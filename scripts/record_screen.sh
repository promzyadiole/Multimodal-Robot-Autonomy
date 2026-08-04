#!/usr/bin/env bash
# Record the simulation demo to a file.
#
#   scripts/record_screen.sh                    whole screen
#   scripts/record_screen.sh --window Gazebo    just the Gazebo window
#   scripts/record_screen.sh --window RViz
#   scripts/record_screen.sh --pick             click a window to choose it
#   scripts/record_screen.sh --out demo.mp4 --fps 30
#
# Stop with q in this terminal, or Ctrl-C.
#
# Why ffmpeg rather than OBS: OBS is the better tool once scenes and overlays
# are wanted, but it needs a GUI session set up by hand before it records
# anything, and this has to be repeatable. Why not Gazebo's own video button:
# it captures the render window alone, so the web interface, RViz and the fact
# that a typed sentence caused the motion are all absent -- which is the whole
# demonstration.
#
# Output is H.264 in an MP4, which LinkedIn, Overleaf and every browser accept
# without conversion. The default preset trades file size for not dropping
# frames while Gazebo is also asking for the GPU.
set -eu

OUT=""
FPS=30
REGION=""
WINDOW=""
PICK=0

while [ $# -gt 0 ]; do
  case "$1" in
    --out)    OUT="$2"; shift 2 ;;
    --fps)    FPS="$2"; shift 2 ;;
    --window) WINDOW="$2"; shift 2 ;;
    --pick)   PICK=1; shift ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "unknown option: $1"; exit 1 ;;
  esac
done

command -v ffmpeg >/dev/null || { echo "ffmpeg is not installed."; exit 1; }
DISPLAY="${DISPLAY:-:1}"
export DISPLAY

# Resolve a window name or a click into the geometry ffmpeg needs. xdotool gives
# the id, xwininfo the absolute position -- ffmpeg's x11grab wants an offset
# from the screen origin, not from the window's parent.
geometry_for() {
  local wid="$1" x y w h
  eval "$(xwininfo -id "$wid" |
    awk '/Absolute upper-left X/{print "x="$4}
         /Absolute upper-left Y/{print "y="$4}
         /Width:/{print "w="$2}
         /Height:/{print "h="$2}')"
  # H.264 requires even dimensions; an odd window silently fails to encode.
  w=$(( w - w % 2 )); h=$(( h - h % 2 ))
  echo "${w}x${h} ${x},${y}"
}

if [ "$PICK" = "1" ]; then
  command -v xwininfo >/dev/null || { echo "xwininfo is not installed."; exit 1; }
  echo "click the window you want to record..."
  wid=$(xwininfo | awk '/Window id:/{print $4}')
  read -r size offset <<EOF
$(geometry_for "$wid")
EOF
  REGION="-video_size $size -i ${DISPLAY}+${offset}"
  echo "  recording that window at $size"
elif [ -n "$WINDOW" ]; then
  command -v xdotool >/dev/null || { echo "xdotool is not installed; use --pick."; exit 1; }
  wid=$(xdotool search --name "$WINDOW" | tail -1)
  [ -n "$wid" ] || { echo "no window matching '$WINDOW'."; exit 1; }
  read -r size offset <<EOF
$(geometry_for "$wid")
EOF
  REGION="-video_size $size -i ${DISPLAY}+${offset}"
  echo "  recording '$WINDOW' at $size"
else
  size=$(xdpyinfo | awk '/dimensions:/{print $2}')
  REGION="-video_size $size -i ${DISPLAY}+0,0"
  echo "  recording the whole screen at $size"
fi

if [ -z "$OUT" ]; then
  mkdir -p recordings
  OUT="recordings/romr_$(date +%Y-%m-%d_%H%M%S).mp4"
fi
mkdir -p "$(dirname "$OUT")"

echo "  -> $OUT   (press q to stop)"
echo ""

# -draw_mouse 1 keeps the cursor, which matters: it is what shows a human
# typing the command rather than a script driving the stack.
# veryfast + crf 20 keeps the encoder off the critical path; Gazebo and the
# encoder competing for CPU is what produces stuttering footage.
exec ffmpeg -hide_banner -loglevel warning -stats \
  -f x11grab -framerate "$FPS" -draw_mouse 1 $REGION \
  -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p \
  -movflags +faststart \
  "$OUT"
