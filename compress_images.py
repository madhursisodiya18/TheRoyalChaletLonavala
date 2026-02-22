import os
from PIL import Image

# Folder to compress
STATIC_DIR = 'static'

# Supported image extensions
EXTENSIONS = ('.jpg', '.jpeg', '.png')

# Compression quality (0-100, lower = smaller file, 85 is a good balance)
JPEG_QUALITY = 85
PNG_OPTIMIZE = True

count = 0
for root, dirs, files in os.walk(STATIC_DIR):
    for file in files:
        if file.lower().endswith(EXTENSIONS):
            path = os.path.join(root, file)
            try:
                img = Image.open(path)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                if file.lower().endswith(('.jpg', '.jpeg')):
                    img.save(path, 'JPEG', quality=JPEG_QUALITY, optimize=True)
                elif file.lower().endswith('.png'):
                    img.save(path, 'PNG', optimize=PNG_OPTIMIZE)
                count += 1
                print(f"Compressed: {path}")
            except Exception as e:
                print(f"Failed to compress {path}: {e}")
print(f"Done. Compressed {count} images.") 