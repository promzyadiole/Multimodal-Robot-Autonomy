from __future__ import annotations

import math
import threading
import time
from typing import Any, Dict, List, Optional

import numpy as np
import rclpy
from action_msgs.msg import GoalStatus
from cv_bridge import CvBridge
from geometry_msgs.msg import PoseStamped, Twist
from nav2_msgs.action import FollowWaypoints, NavigateToPose
from nav2_msgs.srv import ClearEntireCostmap
from nav_msgs.msg import Odometry
from rclpy.action import ActionClient
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, Image, LaserScan
from std_msgs.msg import String
from tf_transformations import quaternion_from_euler

from app.services.state_store import get_state_store


# How stale the last nav2-sourced message may be before we call it not ready.
NAV2_LIVENESS_SEC = 5.0


def quaternion_to_yaw(z: float, w: float) -> float:
    return math.atan2(2.0 * w * z, 1.0 - 2.0 * z * z)


class ROS2Bridge(Node):
    def __init__(self) -> None:
        super().__init__("robot_command_center_bridge")
        self.bridge = CvBridge()
        self.store = get_state_store()

        self.cmd_vel_pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.capture_pub = self.create_publisher(String, "/capture_trigger", 10)

        self.navigate_to_pose_client = ActionClient(
            self, NavigateToPose, "/navigate_to_pose"
        )
        self.follow_waypoints_client = ActionClient(
            self, FollowWaypoints, "/follow_waypoints"
        )

        self.current_nav_goal_handle = None
        self.current_waypoint_goal_handle = None

        # Readiness probe. A node's graph info is only kept current for topics
        # it actually has an endpoint on: without this subscription
        # count_publishers() returned 0 while nav2 was demonstrably serving
        # goals. ActionClient.server_is_ready() is no better -- it stayed True
        # 30 s after nav2 was killed.
        # nav2's lifecycle nodes publish bond heartbeats on /bond continuously
        # while they are up, which is the one signal that is neither cached nor
        # event-driven. /amcl_pose was the obvious candidate but AMCL only
        # publishes when the robot moves past its update thresholds, so a
        # stationary robot looked dead.
        from bond.msg import Status as BondStatus
        self._bond_seen_at: float = 0.0
        self.create_subscription(BondStatus, "/bond", self._bond_callback, 1)

        # Recovery: the obstacle layer accumulates readings of world furniture that
        # the SLAM map does not contain, and can close a doorway behind the robot.
        # Clearing both costmaps is what unsticks it.
        self.clear_global_costmap_client = self.create_client(
            ClearEntireCostmap, "/global_costmap/clear_entirely_global_costmap"
        )
        self.clear_local_costmap_client = self.create_client(
            ClearEntireCostmap, "/local_costmap/clear_entirely_local_costmap"
        )

        self.create_subscription(Odometry, "/odom", self._odom_callback, 10)
        self.create_subscription(LaserScan, "/scan", self._scan_callback, 10)
        self.create_subscription(Image, "/camera/image_raw", self._image_callback, 10)
        self.create_subscription(
            CameraInfo, "/camera/camera_info", self._camera_info_callback, 10
        )

        from geometry_msgs.msg import PoseWithCovarianceStamped

        self.create_subscription(
            PoseWithCovarianceStamped, "/amcl_pose", self._amcl_callback, 10
        )

        self.camera_info = None
        self.get_logger().info("ROS2Bridge initialized.")

    def mark_nav2_ready(self) -> None:
        nav_ready = self.navigate_to_pose_client.wait_for_server(timeout_sec=10.0)
        wp_ready = self.follow_waypoints_client.wait_for_server(timeout_sec=10.0)
        ready = nav_ready and wp_ready
        self.store.set("nav2_ready", ready)

        if ready:
            self.get_logger().info("Nav2 action servers are active.")
        else:
            self.get_logger().error("Nav2 action servers are not ready.")

    def get_current_pose(self) -> Dict[str, Any] | None:
        pose = self.store.get_current_pose()
        if not pose:
            return None

        return {
            "x": pose.get("x"),
            "y": pose.get("y"),
            "yaw": pose.get("yaw"),
            "frame_id": pose.get("frame_id", "map"),
            "timestamp": pose.get("timestamp"),
        }

    def get_scan_summary(self) -> Dict[str, Any]:
        scan = self.store.get("scan", {}) or {}
        return dict(scan)

    def get_odom(self) -> Dict[str, Any]:
        odom = self.store.get("odom", {}) or {}
        return dict(odom)

    def _bond_callback(self, _msg) -> None:
        self._bond_seen_at = time.time()

    def nav2_is_ready(self) -> bool:
        """Probe the action servers now rather than trusting a cached flag.

        mark_nav2_ready() runs once when the bridge is constructed, so if nav2
        starts or stops afterwards that value is simply wrong -- the UI showed
        "nav2 ready" while nav2 was not running at all. server_is_ready() is
        non-blocking, so this is cheap enough to call per request.
        """
        # Judged from heartbeats we actually receive. This process's DDS graph
        # view does not track nav2 coming and going: count_publishers() stayed 0
        # while nav2 was serving goals, and ActionClient.server_is_ready()
        # stayed True 30 s after nav2 was killed.
        ready = (time.time() - self._bond_seen_at) < NAV2_LIVENESS_SEC
        self.store.set("nav2_ready", ready)
        return ready

    def get_robot_status(self) -> Dict[str, Any]:
        current_pose = self.get_current_pose()
        odom = self.get_odom()

        return {
            "nav2_ready": self.nav2_is_ready(),
            "current_pose": current_pose,
            "last_command": self.store.get("last_command"),
            "is_navigating": bool(self.store.get("is_navigating", False)),
            "linear_velocity": odom.get("linear_x"),
            "angular_velocity": odom.get("angular_z"),
        }

    def _amcl_callback(self, msg) -> None:
        yaw = quaternion_to_yaw(
            msg.pose.pose.orientation.z,
            msg.pose.pose.orientation.w,
        )

        pose_data = {
            "x": msg.pose.pose.position.x,
            "y": msg.pose.pose.position.y,
            "yaw": yaw,
            "frame_id": msg.header.frame_id,
            "qz": msg.pose.pose.orientation.z,
            "qw": msg.pose.pose.orientation.w,
        }

        self.store.set("amcl_pose", pose_data)
        self.store.update_pose(
            x=pose_data["x"],
            y=pose_data["y"],
            yaw=pose_data["yaw"],
            frame_id=pose_data["frame_id"],
        )

    def _odom_callback(self, msg: Odometry) -> None:
        self.store.set(
            "odom",
            {
                "linear_x": msg.twist.twist.linear.x,
                "angular_z": msg.twist.twist.angular.z,
            },
        )

    def _scan_callback(self, msg: LaserScan) -> None:
        ranges = np.array(msg.ranges, dtype=np.float32)
        finite = ranges[np.isfinite(ranges)]

        if finite.size == 0:
            summary = {
                "min_distance": None,
                "front_min_distance": None,
                "left_min_distance": None,
                "right_min_distance": None,
                "obstacle_ahead": False,
            }
            self.store.set("scan", summary)
            return

        n = len(ranges)
        front_slice = np.concatenate([ranges[:20], ranges[-20:]])
        left_slice = ranges[n // 4 - 20 : n // 4 + 20]
        right_slice = ranges[(3 * n) // 4 - 20 : (3 * n) // 4 + 20]

        def finite_min(arr: np.ndarray) -> float | None:
            arr = arr[np.isfinite(arr)]
            return float(arr.min()) if arr.size > 0 else None

        front_min = finite_min(front_slice)
        left_min = finite_min(left_slice)
        right_min = finite_min(right_slice)

        summary = {
            "min_distance": float(finite.min()),
            "front_min_distance": front_min,
            "left_min_distance": left_min,
            "right_min_distance": right_min,
            "obstacle_ahead": bool(front_min is not None and front_min < 0.6),
        }
        self.store.set("scan", summary)

    def _image_callback(self, msg: Image) -> None:
        try:
            image = self.bridge.imgmsg_to_cv2(msg, desired_encoding="rgb8")
            self.store.set("latest_image", image)
            self.store.set(
                "latest_image_meta",
                {
                    "frame_id": msg.header.frame_id,
                    "width": msg.width,
                    "height": msg.height,
                    "encoding": msg.encoding,
                },
            )
        except Exception as exc:
            self.get_logger().error(f"Image conversion failed: {exc}")

    def _camera_info_callback(self, msg: CameraInfo) -> None:
        self.camera_info = {
            "frame_id": msg.header.frame_id,
            "width": msg.width,
            "height": msg.height,
            "k": list(msg.k),
            "p": list(msg.p),
        }
        self.store.set("camera_info", self.camera_info)

    def create_pose_stamped(self, x: float, y: float, yaw: float) -> PoseStamped:
        qx, qy, qz, qw = quaternion_from_euler(0.0, 0.0, yaw)
        pose = PoseStamped()
        pose.header.frame_id = "map"
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.pose.position.x = x
        pose.pose.position.y = y
        pose.pose.position.z = 0.0
        pose.pose.orientation.x = qx
        pose.pose.orientation.y = qy
        pose.pose.orientation.z = qz
        pose.pose.orientation.w = qw
        return pose

    def create_pose_stamped_quaternion(
        self,
        x: float,
        y: float,
        qz: float,
        qw: float,
    ) -> PoseStamped:
        pose = PoseStamped()
        pose.header.frame_id = "map"
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.pose.position.x = x
        pose.pose.position.y = y
        pose.pose.position.z = 0.0
        pose.pose.orientation.x = 0.0
        pose.pose.orientation.y = 0.0
        pose.pose.orientation.z = qz
        pose.pose.orientation.w = qw
        return pose

    def navigate_to_pose(self, x: float, y: float, yaw: float) -> Dict[str, Any]:
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = self.create_pose_stamped(x, y, yaw)

        future = self.navigate_to_pose_client.send_goal_async(goal_msg)
        future.add_done_callback(self._navigate_goal_response_callback)

        # cleared here so a caller can wait for THIS goal's outcome
        self.store.set("nav_outcome", None)
        self.store.set("is_navigating", True)
        return {
            "success": True,
            "message": f"Navigation request sent to ({x}, {y}, yaw={yaw}).",
        }

    def navigate_to_pose_quaternion(
        self,
        x: float,
        y: float,
        qz: float,
        qw: float,
    ) -> Dict[str, Any]:
        goal_msg = NavigateToPose.Goal()
        goal_msg.pose = self.create_pose_stamped_quaternion(x, y, qz, qw)

        future = self.navigate_to_pose_client.send_goal_async(goal_msg)
        future.add_done_callback(self._navigate_goal_response_callback)

        self.store.set("is_navigating", True)
        return {
            "success": True,
            "message": f"Navigation request sent to ({x}, {y}, qz={qz}, qw={qw}).",
        }

    def _navigate_goal_response_callback(self, future) -> None:
        try:
            goal_handle = future.result()
            if not goal_handle.accepted:
                self.store.set("is_navigating", False)
                self.get_logger().warning("NavigateToPose goal rejected.")
                return

            self.current_nav_goal_handle = goal_handle
            self.get_logger().info("NavigateToPose goal accepted.")
            result_future = goal_handle.get_result_async()
            result_future.add_done_callback(self._navigate_result_callback)
        except Exception as exc:
            self.store.set("is_navigating", False)
            self.get_logger().error(f"NavigateToPose goal response error: {exc}")

    def _navigate_result_callback(self, future) -> None:
        try:
            result = future.result()
            status = result.status
            self.store.set("is_navigating", False)

            if status == GoalStatus.STATUS_SUCCEEDED:
                self.store.set("nav_outcome", "succeeded")
                self.get_logger().info("NavigateToPose succeeded.")
            elif status == GoalStatus.STATUS_ABORTED:
                self.store.set("nav_outcome", "aborted")
                self.get_logger().warning("NavigateToPose aborted.")
            elif status == GoalStatus.STATUS_CANCELED:
                self.store.set("nav_outcome", "canceled")
                self.get_logger().warning("NavigateToPose canceled.")
            else:
                self.store.set("nav_outcome", f"status_{status}")
                self.get_logger().warning(
                    f"NavigateToPose finished with status {status}."
                )
        except Exception as exc:
            self.store.set("is_navigating", False)
            self.store.set("nav_outcome", "error")
            self.get_logger().error(f"NavigateToPose result error: {exc}")

    def clear_costmaps(self, timeout_sec: float = 5.0) -> Dict[str, Any]:
        """Clear both nav2 costmaps. Used to recover from a stale obstacle layer."""
        cleared, failed = [], []
        for name, client in (
            ("global", self.clear_global_costmap_client),
            ("local", self.clear_local_costmap_client),
        ):
            if not client.wait_for_service(timeout_sec=timeout_sec):
                failed.append(f"{name} (service unavailable)")
                continue
            try:
                client.call_async(ClearEntireCostmap.Request())
                cleared.append(name)
            except Exception as exc:  # noqa: BLE001
                failed.append(f"{name} ({exc})")
        return {
            "success": not failed,
            "cleared": cleared,
            "failed": failed,
            "message": ("Cleared costmaps: " + ", ".join(cleared)) if cleared
                       else "Could not clear any costmap.",
        }

    def follow_waypoints(self, points: List[Dict[str, Any]]) -> Dict[str, Any]:
        goal_msg = FollowWaypoints.Goal()
        goal_msg.poses = [
            self.create_pose_stamped(p["x"], p["y"], p["yaw"]) for p in points
        ]

        future = self.follow_waypoints_client.send_goal_async(goal_msg)
        future.add_done_callback(self._waypoints_goal_response_callback)

        self.store.set("is_navigating", True)
        return {
            "success": True,
            "message": f"Waypoint route request sent with {len(points)} points.",
        }

    def _waypoints_goal_response_callback(self, future) -> None:
        try:
            goal_handle = future.result()
            if not goal_handle.accepted:
                self.store.set("is_navigating", False)
                self.get_logger().warning("FollowWaypoints goal rejected.")
                return

            self.current_waypoint_goal_handle = goal_handle
            self.get_logger().info("FollowWaypoints goal accepted.")
            result_future = goal_handle.get_result_async()
            result_future.add_done_callback(self._waypoints_result_callback)
        except Exception as exc:
            self.store.set("is_navigating", False)
            self.get_logger().error(f"FollowWaypoints goal response error: {exc}")

    def _waypoints_result_callback(self, future) -> None:
        try:
            result = future.result()
            status = result.status
            self.store.set("is_navigating", False)

            if status == GoalStatus.STATUS_SUCCEEDED:
                self.get_logger().info("FollowWaypoints succeeded.")
            elif status == GoalStatus.STATUS_ABORTED:
                self.get_logger().warning("FollowWaypoints aborted.")
            elif status == GoalStatus.STATUS_CANCELED:
                self.get_logger().warning("FollowWaypoints canceled.")
            else:
                self.get_logger().warning(
                    f"FollowWaypoints finished with status {status}."
                )
        except Exception as exc:
            self.store.set("is_navigating", False)
            self.get_logger().error(f"FollowWaypoints result error: {exc}")

    def cancel_navigation(self) -> Dict[str, Any]:
        canceled_any = False

        if self.current_nav_goal_handle is not None:
            self.current_nav_goal_handle.cancel_goal_async()
            canceled_any = True

        if self.current_waypoint_goal_handle is not None:
            self.current_waypoint_goal_handle.cancel_goal_async()
            canceled_any = True

        self.store.set("is_navigating", False)
        return {
            "success": True,
            "message": (
                "Navigation canceled."
                if canceled_any
                else "No active navigation to cancel."
            ),
        }

    def publish_motion(
        self, linear_x: float, angular_z: float, duration_sec: float
    ) -> Dict[str, Any]:
        twist = Twist()
        twist.linear.x = float(linear_x)
        twist.angular.z = float(angular_z)

        end_time = time.time() + max(0.0, duration_sec)
        while time.time() < end_time:
            self.cmd_vel_pub.publish(twist)
            time.sleep(0.1)

        stop = Twist()
        self.cmd_vel_pub.publish(stop)
        return {"success": True, "message": "Motion command executed."}

    def emergency_stop(self) -> Dict[str, Any]:
        self.cancel_navigation()
        stop = Twist()
        self.cmd_vel_pub.publish(stop)
        self.store.set("is_navigating", False)
        return {"success": True, "message": "Robot stopped."}

    def trigger_capture(self, label: str = "manual_capture") -> Dict[str, Any]:
        msg = String()
        msg.data = label
        self.capture_pub.publish(msg)
        return {"success": True, "message": f"Capture trigger published: {label}"}


_ros_bridge_instance: Optional[ROS2Bridge] = None
_ros_thread_started = False


def get_ros2_bridge() -> ROS2Bridge:
    global _ros_bridge_instance, _ros_thread_started

    if _ros_bridge_instance is None:
        if not rclpy.ok():
            rclpy.init()
        _ros_bridge_instance = ROS2Bridge()

    if not _ros_thread_started:
        def _spin() -> None:
            _ros_bridge_instance.mark_nav2_ready()
            rclpy.spin(_ros_bridge_instance)

        thread = threading.Thread(target=_spin, daemon=True)
        thread.start()
        _ros_thread_started = True

    return _ros_bridge_instance