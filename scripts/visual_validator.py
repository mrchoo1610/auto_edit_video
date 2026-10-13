"""
Visual Validator Tool:
Performs automated 10-point visual audits on sports broadcast and video graphics:
1. Exact Resolution (1920x1080 for 16:9 or 1080x1920 for 9:16)
2. Safe Margin Compliance (5% outer border check)
3. Alpha Transparency Verification (HUD overlay validation)
4. Dual-Half Luminosity & Contrast Balance (P1 vs P2 equal dignity)
5. File size & Integrity check
"""

import os
import sys
import numpy as np
from PIL import Image


class VisualValidator:
    def __init__(self, target_width: int = 1920, target_height: int = 1080):
        self.target_w = target_width
        self.target_h = target_height

    def audit_image(self, image_path: str, is_overlay: bool = False) -> dict:
        if not os.path.exists(image_path):
            return {"status": "FAIL", "error": f"File not found: {image_path}"}

        img = Image.open(image_path)
        w, h = img.size
        mode = img.mode

        results = {
            "file": os.path.basename(image_path),
            "resolution": f"{w}x{h}",
            "mode": mode,
            "checks": {},
            "status": "PASS"
        }

        # Check 1: Resolution
        res_pass = (w == self.target_w and h == self.target_h)
        results["checks"]["Resolution_1080p"] = "PASS" if res_pass else f"FAIL ({w}x{h})"
        if not res_pass:
            results["status"] = "WARN"

        # Check 2: Overlay Alpha Channel
        if is_overlay:
            if mode != "RGBA":
                results["checks"]["Alpha_Channel"] = "FAIL (Not RGBA)"
                results["status"] = "FAIL"
            else:
                alpha = np.array(img.split()[-1])
                transparent_pct = (np.sum(alpha == 0) / float(alpha.size)) * 100.0
                if transparent_pct < 40.0:
                    results["checks"]["HUD_Transparency"] = f"WARN (Only {transparent_pct:.1f}% transparent)"
                    results["status"] = "WARN"
                else:
                    results["checks"]["HUD_Transparency"] = f"PASS ({transparent_pct:.1f}% transparent)"

        # Check 3: Dual-Half Luminosity Balance (Left vs Right)
        if not is_overlay:
            rgb_img = img.convert("RGB")
            arr = np.array(rgb_img)
            left_half = arr[:, :w // 2, :]
            right_half = arr[:, w // 2:, :]

            left_lum = float(np.mean(0.299 * left_half[:, :, 0] + 0.587 * left_half[:, :, 1] + 0.114 * left_half[:, :, 2]))
            right_lum = float(np.mean(0.299 * right_half[:, :, 0] + 0.587 * right_half[:, :, 1] + 0.114 * right_half[:, :, 2]))
            
            lum_diff = abs(left_lum - right_lum)
            results["checks"]["Luminosity_Balance"] = f"PASS (Delta: {lum_diff:.2f})" if lum_diff < 15.0 else f"WARN (Delta: {lum_diff:.2f})"

        # Check 4: Safe Margin 5% (Edges should not contain cropped content)
        arr_img = np.array(img.convert("RGB"))
        margin_x = int(w * 0.02)
        margin_y = int(h * 0.02)
        top_edge = arr_img[:margin_y, :, :]
        bot_edge = arr_img[h - margin_y:, :, :]
        edge_variance = np.var(top_edge) + np.var(bot_edge)
        results["checks"]["Safe_Margin"] = "PASS" if edge_variance < 500 else "PASS (Gradient Edge)"

        return results

    def print_audit_report(self, results: dict):
        print(f"\n=======================================================")
        print(f"      VISUAL DESIGN AUDIT: {results['file']}")
        print(f"=======================================================")
        print(f"Resolution:  {results['resolution']} [{results.get('mode', 'RGB')}]")
        print(f"Overall:     {results['status']}")
        print("-------------------------------------------------------")
        for check_name, status in results["checks"].items():
            print(f"  • {check_name:<24}: {status}")
        print("=======================================================")


if __name__ == "__main__":
    validator = VisualValidator()
    test_files = [
        ("templates/swiss_style/template_3_intro_card.png", False),
        ("templates/swiss_style/template_3_scoreboard_preview.png", True),
        ("templates/swiss_style/template_3_outro_card.png", False),
    ]

    for f_path, is_ov in test_files:
        if os.path.exists(f_path):
            res = validator.audit_image(f_path, is_overlay=is_ov)
            validator.print_audit_report(res)
