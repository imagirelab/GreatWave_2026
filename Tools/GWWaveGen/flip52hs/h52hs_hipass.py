# -*- coding: utf-8 -*-
"""Local-contrast view of captured frames (read only): luma minus Gaussian(sigma 12 px) blur, x gain, grey = 0.
2026-10-18 written new (Claude). py -3.10 -B h52hs_hipass.py <in.jpg> <out.png> y0 y1 [gain]"""
import sys
import numpy as np
from PIL import Image
from scipy import ndimage
a = np.asarray(Image.open(sys.argv[1]).convert("YCbCr"))[..., 0].astype(np.float64)
y0, y1 = int(sys.argv[3]), int(sys.argv[4]); g = float(sys.argv[5]) if len(sys.argv) > 5 else 12.0
a = a[y0:y1]
hp = a - ndimage.gaussian_filter(a, 12)
print("hipass rms levels %.2f  p99 |.| %.2f" % (hp.std(), np.percentile(np.abs(hp), 99)))
Image.fromarray(np.clip(128 + g * hp, 0, 255).astype(np.uint8)).save(sys.argv[2])
