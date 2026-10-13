"""
Hardware Profiler & Render Engine Optimizer
Automatically inspects system configuration (CPU, RAM, GPU) and probes
FFmpeg hardware-accelerated encoders to choose the optimal rendering technology.
"""

import os
import subprocess
import platform
import ctypes
from dataclasses import dataclass
from typing import List, Tuple, Optional
import imageio_ffmpeg


@dataclass
class HardwareProfile:
    cpu_name: str
    cpu_cores: int
    total_ram_gb: float
    avail_ram_gb: float
    gpu_names: List[str]
    selected_encoder: str
    encoder_name: str
    ffmpeg_encoder_args: List[str]
    performance_estimate: str
    description: str


class HardwareProfiler:
    def __init__(self, ffmpeg_exe: Optional[str] = None):
        self.ffmpeg_exe = ffmpeg_exe or imageio_ffmpeg.get_ffmpeg_exe()

    def get_ram_info(self) -> Tuple[float, float]:
        """Returns (total_ram_gb, available_ram_gb)"""
        try:
            if platform.system() == "Windows":
                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ('dwLength', ctypes.c_ulong),
                        ('dwMemoryLoad', ctypes.c_ulong),
                        ('ullTotalPhys', ctypes.c_ulonglong),
                        ('ullAvailPhys', ctypes.c_ulonglong),
                        ('ullTotalPageFile', ctypes.c_ulonglong),
                        ('ullAvailPageFile', ctypes.c_ulonglong),
                        ('ullTotalVirtual', ctypes.c_ulonglong),
                        ('ullAvailVirtual', ctypes.c_ulonglong),
                        ('ullAvailExtendedVirtual', ctypes.c_ulonglong),
                    ]
                stat = MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
                total_gb = stat.ullTotalPhys / (1024 ** 3)
                avail_gb = stat.ullAvailPhys / (1024 ** 3)
                return round(total_gb, 1), round(avail_gb, 1)
        except Exception:
            pass
        return 16.0, 8.0

    def get_gpu_names(self) -> List[str]:
        """Detects installed graphics cards"""
        gpus = []
        try:
            if platform.system() == "Windows":
                # PowerShell query for video controller
                cmd = ["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_VideoController).Name"]
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
                if res.returncode == 0:
                    for line in res.stdout.splitlines():
                        name = line.strip()
                        if name and name not in gpus:
                            gpus.append(name)
        except Exception:
            pass

        if not gpus:
            # Fallback nvidia-smi
            try:
                res = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=3)
                if res.returncode == 0:
                    for line in res.stdout.splitlines():
                        name = line.strip()
                        if name and name not in gpus:
                            gpus.append(name)
            except Exception:
                pass

        return gpus if gpus else ["Standard Graphics Adapter"]

    def test_ffmpeg_encoder(self, encoder: str, extra_args: List[str]) -> bool:
        """Lightweight probe testing if FFmpeg can encode with the given codec"""
        try:
            cmd = [
                self.ffmpeg_exe, "-y",
                "-f", "lavfi", "-i", "nullsrc=s=256x256:d=0.1:r=30",
                "-pix_fmt", "yuv420p",
                "-c:v", encoder,
                *extra_args,
                "-f", "null", "-"
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=4)
            return res.returncode == 0
        except Exception:
            return False

    def profile_and_optimize(self) -> HardwareProfile:
        """
        Analyzes hardware capabilities and determines the optimal rendering technology.
        """
        cpu_name = platform.processor() or "Unknown CPU"
        cpu_cores = os.cpu_count() or 4
        total_ram, avail_ram = self.get_ram_info()
        gpus = self.get_gpu_names()

        # Candidates in priority order
        candidates = [
            (
                "NVIDIA NVENC (GPU)",
                "h264_nvenc",
                ["-c:v", "h264_nvenc", "-preset", "p1", "-tune", "ll", "-cq", "22"],
                "~90 - 130 FPS (Tang toc phan cung GPU NVIDIA NVENC)",
                "NVIDIA GPU Dedicated Hardware Encoding (Toi uu do tre thap & toc do sieu nhanh)"
            ),
            (
                "Intel QuickSync (GPU/iGPU)",
                "h264_qsv",
                ["-c:v", "h264_qsv", "-global_quality", "22", "-preset", "veryfast"],
                "~70 - 100 FPS (Tang toc phan cung Intel QSV)",
                "Intel Hardware Accelerated Encoding"
            ),
            (
                "AMD AMF (GPU)",
                "h264_amf",
                ["-c:v", "h264_amf", "-quality", "speed", "-rc", "cqp", "-qp_i", "22", "-qp_p", "22"],
                "~60 - 90 FPS (Tang toc phan cung AMD AMF)",
                "AMD Advanced Media Framework Hardware Encoding"
            ),
            (
                "Apple VideoToolbox (GPU/NE)",
                "h264_videotoolbox",
                ["-c:v", "h264_videotoolbox", "-q:v", "65"],
                "~80 - 120 FPS (Tang toc phan cung Apple Silicon)",
                "Apple VideoToolbox Hardware Encoding"
            ),
        ]

        for display_name, enc_codec, enc_args, perf_est, desc in candidates:
            if self.test_ffmpeg_encoder(enc_codec, enc_args[2:]):
                return HardwareProfile(
                    cpu_name=cpu_name,
                    cpu_cores=cpu_cores,
                    total_ram_gb=total_ram,
                    avail_ram_gb=avail_ram,
                    gpu_names=gpus,
                    selected_encoder=enc_codec,
                    encoder_name=display_name,
                    ffmpeg_encoder_args=enc_args,
                    performance_estimate=perf_est,
                    description=desc
                )

        # Fallback to multi-threaded CPU software encoding
        thread_count = min(cpu_cores, 16)
        cpu_args = ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "22", "-threads", str(thread_count)]
        return HardwareProfile(
            cpu_name=cpu_name,
            cpu_cores=cpu_cores,
            total_ram_gb=total_ram,
            avail_ram_gb=avail_ram,
            gpu_names=gpus,
            selected_encoder="libx264",
            encoder_name=f"CPU Software Multi-Threading ({thread_count} Threads)",
            ffmpeg_encoder_args=cpu_args,
            performance_estimate="~30 - 50 FPS (Xu ly da luong CPU)",
            description=f"CPU libx264 Ultrafast ({thread_count} threads)"
        )

    def print_profile_banner(self, profile: HardwareProfile):
        """Prints a professional hardware & render technology profile"""
        gpu_str = ", ".join(profile.gpu_names) if profile.gpu_names else "N/A"
        lines = [
            "==================================================================",
            "          KIEM TRA CAU HINH & TOI UU HOA RENDER ENGINE           ",
            "==================================================================",
            f"CPU:          {profile.cpu_cores} Logical Cores ({profile.cpu_name[:40]})",
            f"Bo nho RAM:   {profile.total_ram_gb:.1f} GB (Kha dung: {profile.avail_ram_gb:.1f} GB)",
            f"Card do hoa:  {gpu_str}",
            f"Cong nghe:    {profile.encoder_name}",
            f"Chi tiet:     {profile.description}",
            f"Toc do render: {profile.performance_estimate}",
            "------------------------------------------------------------------"
        ]
        for l in lines:
            try:
                print(l)
            except Exception:
                try:
                    print(l.encode('ascii', errors='replace').decode('ascii'))
                except Exception:
                    pass
