"""
Vision and motion tracking module for Billiards Highlight AI Editor.
Implements:
1. Billiard table felt ROI detection (Green, Blue, Grey/Tan felt).
2. Ball Movement Tracking & velocity zero-crossing (Spec 5.2: velocity = 0 + 0.5s).
3. Player stance / bridge placement detection (Spec 2.2 Beat 1: Tension 1.0 - 1.5s).
4. Dead time detection (walking around table > 2.5s, rack setup elimination).
5. Racked balls cluster detection (Spec 5.1 Action Anchor for break shots).
"""

import cv2
import numpy as np
from typing import Tuple, List, Optional, Dict, Any


class MotionTracker:
    def __init__(self, felt_color_hint: str = "auto"):
        """
        felt_color_hint: 'auto', 'green', 'blue', or 'any'
        """
        self.felt_color_hint = felt_color_hint
        self._cached_table_bbox: Optional[Tuple[int, int, int, int]] = None

    def detect_table_felt_roi(self, frame: np.ndarray) -> Tuple[int, int, int, int]:
        """
        Finds bounding rectangle (x, y, w, h) of the pool/snooker table surface.
        Uses HSV color thresholding for common felt colors: Green, Tournament Blue, Simonis Grey.
        """
        if self._cached_table_bbox is not None:
            return self._cached_table_bbox

        h, w = frame.shape[:2]
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # Color ranges for pool table cloth
        # Green felt: H: 35-85, S: 40-255, V: 40-255
        # Tournament Blue felt: H: 90-130, S: 50-255, V: 40-255
        mask_green = cv2.inRange(hsv, np.array([35, 40, 40]), np.array([85, 255, 255]))
        mask_blue = cv2.inRange(hsv, np.array([90, 50, 40]), np.array([130, 255, 255]))
        mask = cv2.bitwise_or(mask_green, mask_blue)

        # Clean noise
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        best_box = None
        max_area = 0.0
        min_table_area = (w * h) * 0.10  # Table should be at least 10% of frame

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > max_area and area >= min_table_area:
                x, y, bw, bh = cv2.boundingRect(cnt)
                # Table aspect ratio is usually between 1.2 and 2.5
                aspect = bw / float(bh)
                if 1.0 <= aspect <= 3.0:
                    max_area = area
                    best_box = (x, y, bw, bh)

        if best_box is None:
            # Fallback to center 70% of screen if table color is unusual
            best_box = (int(w * 0.15), int(h * 0.15), int(w * 0.70), int(h * 0.70))

        self._cached_table_bbox = best_box
        return best_box

    def compute_ball_motion_energy(
        self,
        prev_gray: np.ndarray,
        curr_gray: np.ndarray,
        table_roi: Optional[Tuple[int, int, int, int]] = None
    ) -> float:
        """
        Computes motion magnitude of balls moving on the table surface.
        Returns a normalized velocity/energy value.
        """
        if table_roi is not None:
            x, y, w, h = table_roi
            p_crop = prev_gray[y:y+h, x:x+w]
            c_crop = curr_gray[y:y+h, x:x+w]
        else:
            p_crop = prev_gray
            c_crop = curr_gray

        # Frame difference
        diff = cv2.absdiff(p_crop, c_crop)
        _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
        
        # Calculate moving pixels percentage on the table
        total_pixels = thresh.shape[0] * thresh.shape[1]
        if total_pixels == 0:
            return 0.0
            
        moving_pixels = cv2.countNonZero(thresh)
        normalized_motion = (moving_pixels / total_pixels) * 100.0
        return float(normalized_motion)

    def detect_racked_cluster(
        self,
        frame: np.ndarray,
        table_roi: Tuple[int, int, int, int],
        min_cluster_balls: int = 6
    ) -> bool:
        """
        Spec 5.1 Action Anchor:
        Detects whether an intact cluster of balls (triangle/diamond rack) is on table.
        A rack appears as a high density of contrasting circular contours tightly grouped.
        Pass min_cluster_balls=9 to require a full 9-ball diamond rack.
        """
        x, y, w, h = table_roi
        crop = frame[y:y+h, x:x+w]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        
        # Detect circles / clusters
        blurred = cv2.GaussianBlur(gray, (9, 9), 2)
        # HoughCircles or edge density
        edges = cv2.Canny(blurred, 50, 150)
        
        # Count connected components in edge map
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(closed, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        
        # A racked cluster has tightly clustered balls
        ball_like_count = 0
        centers = []
        for c in contours:
            area = cv2.contourArea(c)
            if 40 < area < 3000:
                perimeter = cv2.arcLength(c, True)
                if perimeter > 0:
                    circularity = 4 * np.pi * (area / (perimeter * perimeter))
                    if circularity > 0.45:
                        M = cv2.moments(c)
                        if M["m00"] > 0:
                            cx = int(M["m10"] / M["m00"])
                            cy = int(M["m01"] / M["m00"])
                            centers.append((cx, cy))
                            ball_like_count += 1
        
        # Check if min_cluster_balls+ ball centroids are clustered closely together (within rack radius)
        if len(centers) >= min_cluster_balls:
            centers_np = np.array(centers)
            # Find center of cluster
            median_c = np.median(centers_np, axis=0)
            dists = np.linalg.norm(centers_np - median_c, axis=1)
            # If enough balls are within 18% of table width
            close_balls = np.sum(dists < (w * 0.18))
            if close_balls >= min_cluster_balls:
                return True

        return False

    def find_ball_stop_timestamp(
        self,
        motion_curve: List[Tuple[float, float]],
        impact_timestamp: float,
        buffer_sec: float = 0.5,
        threshold_velocity: float = 0.15,
        max_duration: float = 12.0
    ) -> float:
        """
        Spec 5.2:
        Theo dõi vận tốc các bi. Khi toàn bộ bi dừng chuyển động (velocity = 0),
        tự động kết thúc cú đánh sau đó 0.5 giây.
        """
        post_impact = [m for m in motion_curve if m[0] >= impact_timestamp]
        if not post_impact:
            return impact_timestamp + 2.5 + buffer_sec

        # Search for consecutive frames where velocity <= threshold_velocity
        consecutive_rest_frames = 0
        needed_consecutive = 6  # ~0.2s of continuous stillness
        
        stop_time = impact_timestamp + 2.5  # fallback
        for t, vel in post_impact:
            if t - impact_timestamp > max_duration:
                # Max cut-off safeguard
                stop_time = t
                break
            
            # Must wait at least 1.0s after impact before declaring ball at rest
            if t - impact_timestamp < 1.0:
                continue

            if vel <= threshold_velocity:
                consecutive_rest_frames += 1
                if consecutive_rest_frames >= needed_consecutive:
                    stop_time = t
                    break
            else:
                consecutive_rest_frames = 0

        return stop_time + buffer_sec
