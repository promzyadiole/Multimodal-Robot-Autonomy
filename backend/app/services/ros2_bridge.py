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

        # The Gazebo camera plugin publishes under its own name, so the frames
        # arrive on /camera/romr_camera/image_raw. Subscribing to the shorter
        # /camera/image_raw succeeds and then silently receives nothing -- ROS
        # does not warn about a subscription with no publisher, so the vision
        # page simply reported "no annotated image available" as though the
        # detector had found nothing, rather than as though it had never been
        # given a frame. Both names are taken: the plugin's is what this world
        # produces, and the short one keeps working if the topic is remapped.
        for topic in ("/camera/romr_camera/image_raw", "/camera/image_raw"):
            self.create_subscription(Image, topic, self._image_callback, 10)
        for topic in ("/camera/romr_camera/camera_info", "/camera/camera_info"):
            self.create_subscription(
                CameraInfo, topic, self._camera_info_callback, 10
            )

        from geometry_msgs.msg import PoseWithCovarianceStamped
        from rclpy.qos import (QoSDurabilityPolicy, QoSHistoryPolicy, QoSProfile,
                               QoSReliabilityPolicy)

        # AMCL latches its last pose, and only publishes again once the robot
        # moves. Subscribing volatile means a backend restarted while the robot
        # is parked receives nothing at all and reports "no pose estimate
        # published yet" indefinitely, despite localisation being fine.
        # Matching the publisher's durability delivers that last pose on
        # connection.
        self.create_subscription(
            PoseWithCovarianceStamped, "/amcl_pose", self._amcl_callback,
            QoSProfile(depth=1,
                       durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
                       reliability=QoSReliabilityPolicy.RELIABLE,
                       history=QoSHistoryPolicy.KEEP_LAST),
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
            "localisation": self.get_localisation_confidence(),
        }

    # ---- localisation confidence ---------------------------------------
    #
    # AMCL cannot tell you that its estimate has become wrong -- a particle
    # filter maintains a belief and corrects it incrementally, and every
    # consumer downstream (planner, controller, goal checker) treats that
    # belief as fact. Measured on this system, belief and ground truth
    # diverged by up to 15.5 m while nav2 continued to report goals as
    # succeeded, and 83% of reported successes were false.
    #
    # The filter does, however, publish the covariance of its own estimate.
    # A spread population is the filter saying it is unsure, and that signal
    # was simply not being read. This does not fix divergence -- a confidently
    # wrong filter still reports a tight covariance -- but it converts a
    # silent failure into a reported one, which is the difference between a
    # robot that lies and a robot that says "I do not know where I am".

    # 1 sigma, metres and radians, beyond which the estimate is not trusted
    POSITION_SIGMA_LIMIT = 0.60
    YAW_SIGMA_LIMIT = 0.35

    def _record_confidence(self, covariance) -> None:
        """Extract the diagonal of the 6x6 pose covariance AMCL publishes."""
        try:
            cov = list(covariance)
            var_x, var_y, var_yaw = cov[0], cov[7], cov[35]
        except Exception:  # noqa: BLE001
            return
        sigma_x = math.sqrt(max(var_x, 0.0))
        sigma_y = math.sqrt(max(var_y, 0.0))
        sigma_yaw = math.sqrt(max(var_yaw, 0.0))
        self.store.set(
            "amcl_confidence",
            {
                "sigma_x": round(sigma_x, 4),
                "sigma_y": round(sigma_y, 4),
                "sigma_yaw": round(sigma_yaw, 4),
                # a single scalar for the UI: the larger positional spread
                "position_sigma": round(max(sigma_x, sigma_y), 4),
                "confident": (
                    max(sigma_x, sigma_y) <= self.POSITION_SIGMA_LIMIT
                    and sigma_yaw <= self.YAW_SIGMA_LIMIT
                ),
                "at": time.time(),
            },
        )

    def get_localisation_confidence(self) -> Dict[str, Any]:
        c = self.store.get("amcl_confidence")
        if not c:
            return {"known": False, "confident": None,
                    "reason": "no pose estimate published yet"}
        # AMCL publishes /amcl_pose on update, not on a timer, and a particle
        # filter only updates once the robot has moved past update_min_d. A
        # parked robot therefore has an arbitrarily old estimate that is
        # perfectly correct, so age on its own is not evidence of anything --
        # a robot left alone for six minutes was being reported as not
        # confident while its particle cloud sat at 0.09 rad, which made the
        # answer node refuse to confirm arrivals it should have confirmed.
        #
        # What would be evidence is the robot having moved without AMCL
        # saying anything about it. That is the condition tested here: stale
        # means driving with no pose update, not merely time passing.
        age = time.time() - c.get("at", 0.0)
        last_motion = self.store.get("last_motion_at") or 0.0
        moved_since_update = last_motion - c.get("at", 0.0)
        stale = moved_since_update > 15.0
        confident = bool(c["confident"]) and not stale
        if stale:
            reason = (
                f"robot has been driving for {moved_since_update:.0f} s with no "
                "pose update -- has AMCL stopped?"
            )
        elif c["confident"]:
            reason = "particle spread within limits"
        else:
            reason = (
                f"particle spread too wide: position sigma "
                f"{c['position_sigma']:.2f} m (limit {self.POSITION_SIGMA_LIMIT}), "
                f"yaw sigma {c['sigma_yaw']:.2f} rad (limit {self.YAW_SIGMA_LIMIT})"
            )
        return {"known": True, "confident": confident, "reason": reason,
                "age_sec": round(age, 1), **{k: c[k] for k in
                ("sigma_x", "sigma_y", "sigma_yaw", "position_sigma")}}

    def is_localised(self) -> bool:
        return bool(self.get_localisation_confidence().get("confident"))

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

        self._record_confidence(msg.pose.covariance)
        self.store.set("amcl_pose", pose_data)
        self.store.update_pose(
            x=pose_data["x"],
            y=pose_data["y"],
            yaw=pose_data["yaw"],
            frame_id=pose_data["frame_id"],
        )

    # Below this the robot is standing still, not creeping. Measured drift on a
    # parked robot is about 2 mm/min, well under this.
    MOVING_LINEAR = 0.01
    MOVING_ANGULAR = 0.02

    def _odom_callback(self, msg: Odometry) -> None:
        lin = msg.twist.twist.linear.x
        ang = msg.twist.twist.angular.z
        moving = abs(lin) > self.MOVING_LINEAR or abs(ang) > self.MOVING_ANGULAR
        if moving:
            # Timestamped so localisation staleness can be judged against
            # whether the robot has actually moved, rather than against a clock.
            self.store.set("last_motion_at", time.time())
        self.store.set(
            "odom",
            {"linear_x": lin, "angular_z": ang, "moving": moving},
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

    # Encodings this camera can emit, and how many bytes per pixel each uses.
    # Anything outside this set falls back to cv_bridge.
    _CHANNELS = {"rgb8": 3, "bgr8": 3, "rgba8": 4, "bgra8": 4, "mono8": 1}

    @staticmethod
    def _to_rgb8(msg: Image):
        """Decode a ROS Image into an RGB8 array without going through cv_bridge.

        cv_bridge is a C++ extension built against the NumPy that shipped with
        the distribution, and this environment runs NumPy 2. Calling it raises
        "Boost.Python.function object returned a result with an exception set",
        which names neither NumPy nor the image, and arrives once per frame at
        camera rate. The vision page then reports no objects in view -- the
        detector is working perfectly and has simply never been handed a frame.

        The message is a flat buffer with known width, height and encoding, so
        the conversion is a reshape and at most a channel swap. Doing it here
        removes the dependency rather than pinning the whole backend's NumPy to
        satisfy one function.
        """
        n = ROS2Bridge._CHANNELS.get(msg.encoding)
        if n is None:
            return None
        arr = np.frombuffer(msg.data, dtype=np.uint8)
        # step is the row stride in bytes and may exceed width * n for padding.
        expected = msg.height * msg.step
        if arr.size < expected:
            return None
        arr = arr[:expected].reshape(msg.height, msg.step)[:, : msg.width * n]
        arr = arr.reshape(msg.height, msg.width, n)
        if msg.encoding == "mono8":
            return np.repeat(arr, 3, axis=2)
        if msg.encoding in ("bgr8", "bgra8"):
            return arr[:, :, 2::-1] if n == 4 else arr[:, :, ::-1]
        return arr[:, :, :3]

    def _image_callback(self, msg: Image) -> None:
        try:
            image = self._to_rgb8(msg)
            if image is None:
                image = self.bridge.imgmsg_to_cv2(msg, desired_encoding="rgb8")
            self.store.set("latest_image", np.ascontiguousarray(image))
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