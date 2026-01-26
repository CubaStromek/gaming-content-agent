import zipfile
import os

theme_dir = r'C:\AI\gaming-content-agent\wp-theme-gameinfo'
zip_path = r'C:\AI\gaming-content-agent\news_info.zip'

# Remove old zip
if os.path.exists(zip_path):
    os.remove(zip_path)

# Create new zip with forward slashes
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(theme_dir):
        for file in files:
            file_path = os.path.join(root, file)
            # Use forward slashes and new folder name
            rel_path = os.path.relpath(file_path, theme_dir)
            arcname = 'news_info/' + rel_path.replace(os.sep, '/')
            zf.write(file_path, arcname)
            print(f'Added: {arcname}')

print(f'\nZIP created: {zip_path}')
