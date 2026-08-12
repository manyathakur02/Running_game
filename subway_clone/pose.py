"""
Step 3: Pose detection exploration.

This script does NOT touch the game. Its only job is to help you see,
concretely, how your body's landmark coordinates move when you lean,
jump, and duck -- so the thresholds we write in Step 4 are based on real
observed ranges instead of guesses.

Run this, stand in frame, and try:
  - leaning left / right
  - jumping in place
  - ducking / crouching

Watch the printed values for LEFT_SHOULDER_X, MID_SHOULDER_Y, and
MID_HIP_Y in the terminal, and note roughly:
  - how far mid_shoulder_x moves left/right when you lean a full lane-width
  - how much mid_shoulder_y drops when you jump vs. rises when you duck

Press 'q' with the video window focused to quit.
"""

import cv2
import mediapipe as mp

mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils

# Landmark indices we actually care about for gesture control.
# (Full list: https://google.github.io/mediapipe/solutions/pose.html)
LEFT_SHOULDER = mp_pose.PoseLandmark.LEFT_SHOULDER
RIGHT_SHOULDER = mp_pose.PoseLandmark.RIGHT_SHOULDER
LEFT_HIP = mp_pose.PoseLandmark.LEFT_HIP
RIGHT_HIP = mp_pose.PoseLandmark.RIGHT_HIP


def main():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: could not open webcam. Check camera index / permissions.")
        return

    print_counter = 0

    with mp_pose.Pose(
        model_complexity=1,
        min_detection_confidence=0.6,
        min_tracking_confidence=0.6,
    ) as pose:
        while cap.isOpened():
            ok, frame = cap.read()
            if not ok:
                print("Frame grab failed, stopping.")
                break

            # Mirror the frame so movement feels natural (like a mirror,
            # not a camera behind you) -- important for game controls.
            frame = cv2.flip(frame, 1)

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = pose.process(rgb)

            if results.pose_landmarks:
                mp_drawing.draw_landmarks(
                    frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS
                )

                lm = results.pose_landmarks.landmark
                mid_shoulder_x = (lm[LEFT_SHOULDER].x + lm[RIGHT_SHOULDER].x) / 2
                mid_shoulder_y = (lm[LEFT_SHOULDER].y + lm[RIGHT_SHOULDER].y) / 2
                mid_hip_y = (lm[LEFT_HIP].y + lm[RIGHT_HIP].y) / 2

                # Print roughly 4x/sec instead of every frame -- readable.
                print_counter += 1
                if print_counter % 15 == 0:
                    print(
                        f"mid_shoulder_x={mid_shoulder_x:.3f}  "
                        f"mid_shoulder_y={mid_shoulder_y:.3f}  "
                        f"mid_hip_y={mid_hip_y:.3f}"
                    )

                # Draw a crosshair at mid-shoulder so you can visually
                # confirm what the numbers correspond to.
                h, w, _ = frame.shape
                cx, cy = int(mid_shoulder_x * w), int(mid_shoulder_y * h)
                cv2.circle(frame, (cx, cy), 8, (0, 255, 0), -1)

            cv2.putText(
                frame,
                "Press 'q' to quit",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2,
            )
            cv2.imshow("Pose Exploration", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()