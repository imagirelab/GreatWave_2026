"""contour -- base contour (基準輪郭) extraction and contour metrics.

Owned by the contour / test agents.  The foundation only creates the package.
Conventions to follow (see gw.frame): continuous pixel coordinates with the origin at
the top-left corner, H-normalised (X_H, Z_H) scene coordinates, lengths in % of image
height.  Output goes to target/ (base_contour.json, candidates/a, candidates/b) and
results/step1_prepare/.
"""
