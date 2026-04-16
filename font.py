#!/usr/bin/env python3
"""
CS2 Font Replacer for Linux
Replaces Counter-Strike 2 fonts with a custom font and adjusts sizing
"""

import os
import sys
import shutil
import re
from pathlib import Path

def find_cs2_path():
    """Find CS2 installation directory"""
    common_paths = [
        Path.home() / "/z/SteamLibrary/steamapps/common/Counter-Strike Global Offensive",
        Path.home() / ".steam/steam/steamapps/common/Counter-Strike Global Offensive",
        Path.home() / ".local/share/Steam/steamapps/common/Counter-Strike Global Offensive",
        Path("/usr/share/steam/steamapps/common/Counter-Strike Global Offensive"),
    ]
    
    for path in common_paths:
        if path.exists():
            return path
    
    return None

def list_fonts(font_dir):
    """List all files in font directory recursively"""
    print(f"\nScanning: {font_dir}")
    all_files = list(font_dir.rglob("*"))
    all_files = [f for f in all_files if f.is_file()]
    
    if not all_files:
        print("Directory is empty!")
        return []
    
    print(f"\nFound {len(all_files)} files:")
    for f in all_files:
        rel_path = f.relative_to(font_dir)
        print(f"  - {rel_path} ({f.stat().st_size} bytes)")
    
    return all_files

def backup_fonts(font_dir, backup_dir):
    """Backup original fonts"""
    if not backup_dir.exists():
        backup_dir.mkdir(parents=True)
        print(f"Creating backup directory: {backup_dir}")
    
    # Look for all font file types recursively
    font_patterns = ["**/*.ttf", "**/*.otf", "**/*.vfont", "**/*.woff", "**/*.woff2"]
    fonts_backed_up = 0
    
    for pattern in font_patterns:
        for font_file in font_dir.glob(pattern):
            # Preserve directory structure in backup
            rel_path = font_file.relative_to(font_dir)
            backup_file = backup_dir / rel_path
            backup_file.parent.mkdir(parents=True, exist_ok=True)
            
            if not backup_file.exists():
                shutil.copy2(font_file, backup_file)
                fonts_backed_up += 1
                print(f"Backed up: {rel_path}")
    
    return fonts_backed_up

def replace_fonts(font_dir, replacement_font):
    """Replace CS2 fonts with the specified font"""
    if not os.path.exists(replacement_font):
        print(f"Error: Font file '{replacement_font}' not found!")
        return False
    
    # Look for all font files recursively
    font_patterns = ["**/*.ttf", "**/*.otf", "**/*.vfont", "**/*.woff", "**/*.woff2"]
    font_files = []
    
    for pattern in font_patterns:
        font_files.extend(list(font_dir.glob(pattern)))
    
    if not font_files:
        print(f"\nNo font files found in {font_dir}")
        print("\nLet me check what's actually in this directory:")
        list_fonts(font_dir)
        return False
    
    replaced = 0
    for font_file in font_files:
        try:
            rel_path = font_file.relative_to(font_dir)
            shutil.copy2(replacement_font, font_file)
            replaced += 1
            print(f"Replaced: {rel_path}")
        except Exception as e:
            print(f"Error replacing {font_file.name}: {e}")
    
    return replaced > 0

def find_style_files(panorama_dir):
    """Find style-related files in Panorama directory"""
    # Look for various file types that might contain styling
    patterns = ["**/*.css", "**/*.vcss_c", "**/*.xml", "**/*.vxml_c", "**/*.txt", "**/*.cfg"]
    style_files = []
    
    print(f"\nSearching for style files in: {panorama_dir}")
    
    for pattern in patterns:
        files = list(panorama_dir.glob(pattern))
        if files:
            print(f"  Found {len(files)} {pattern} files")
            style_files.extend(files)
    
    return style_files

def find_vpk_files(cs2_path):
    """Find VPK archive files"""
    vpk_files = []
    game_dir = cs2_path / "game/csgo"
    
    if game_dir.exists():
        vpk_files = list(game_dir.glob("pak01_dir.vpk"))
        vpk_files.extend(list(game_dir.glob("*.vpk")))
    
    return vpk_files

def backup_style_files(style_files, backup_dir):
    """Backup style files"""
    backup_style_dir = backup_dir / "style_backup"
    backup_style_dir.mkdir(parents=True, exist_ok=True)
    
    backed_up = 0
    for style_file in style_files:
        # Create a unique backup name using full path
        backup_name = str(style_file).replace('/', '_').replace('\\', '_').replace(':', '_')
        backup_file = backup_style_dir / backup_name
        
        if not backup_file.exists():
            shutil.copy2(style_file, backup_file)
            backed_up += 1
    
    return backed_up

def adjust_fontconfig_pixelsize(conf_file, scale_factor, font_family=None):
    """Add or modify pixelsize scaling in a fontconfig XML file"""
    try:
        with open(conf_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if there's already a pixelsize rule
        if '<edit name="pixelsize"' in content:
            print(f"  {conf_file.name} already has pixelsize rules")
            # Update existing scale factor
            pattern = re.compile(r'(<double>)([\d.]+)(</double>)')
            content = pattern.sub(lambda m: f'{m.group(1)}{scale_factor}{m.group(3)}', content)
        else:
            # Add new pixelsize scaling rule
            rule = f'''
	<!-- Added by CS2 Font Replacer -->
	<match target="font">'''
            
            if font_family:
                rule += f'''
		<test name="family">
			<string>{font_family}</string>
		</test>'''
            
            rule += f'''
		<edit name="pixelsize" mode="assign">
			<times>
				<name>pixelsize</name>
				<double>{scale_factor}</double>
			</times>
		</edit>
	</match>
'''
            
            # Insert before closing </fontconfig> tag
            content = content.replace('</fontconfig>', rule + '</fontconfig>')
        
        with open(conf_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return True
    except Exception as e:
        print(f"  Error modifying {conf_file.name}: {e}")
        return False

def adjust_fontconfig_files(font_dir, scale_factor, font_family=None):
    """Adjust pixelsize in fontconfig .conf files"""
    conf_dir = font_dir / "conf.d"
    
    if not conf_dir.exists():
        print(f"No conf.d directory found at {conf_dir}")
        return 0
    
    # Look for valve.conf or create/modify it
    valve_conf = conf_dir / "95-valve.conf"
    custom_conf = conf_dir / "96-custom-scale.conf"
    
    modified = 0
    
    if valve_conf.exists():
        print(f"\nModifying {valve_conf.name}...")
        if adjust_fontconfig_pixelsize(valve_conf, scale_factor, font_family):
            modified += 1
    else:
        # Create a new config file
        print(f"\nCreating {custom_conf.name}...")
        custom_conf.write_text(f'''<?xml version='1.0'?>
<!DOCTYPE fontconfig SYSTEM 'fonts.dtd'>
<fontconfig>
	<!-- Custom font scaling -->
	<match target="font">
		<edit name="pixelsize" mode="assign">
			<times>
				<name>pixelsize</name>
				<double>{scale_factor}</double>
			</times>
		</edit>
	</match>
</fontconfig>
''')
        modified += 1
    
    return modified

def restore_fonts(font_dir, backup_dir):
    """Restore original fonts from backup"""
    if not backup_dir.exists():
        print("No backup found!")
        return False
    
    restored = 0
    for backup_file in backup_dir.rglob("*"):
        if backup_file.is_file() and backup_file.parent.name != "css_backup":
            rel_path = backup_file.relative_to(backup_dir)
            target_file = font_dir / rel_path
            target_file.parent.mkdir(parents=True, exist_ok=True)
            
            try:
                shutil.copy2(backup_file, target_file)
                restored += 1
                print(f"Restored: {rel_path}")
            except Exception as e:
                print(f"Error restoring {rel_path}: {e}")
    
    return restored > 0

def restore_style_files(panorama_dir, backup_dir):
    """Restore style files from backup"""
    backup_style_dir = backup_dir / "style_backup"
    
    if not backup_style_dir.exists():
        print("No style file backup found!")
        return False
    
    restored = 0
    for backup_file in backup_style_dir.glob("*"):
        if backup_file.is_file():
            # Reconstruct original path from backup name
            original_path = str(backup_file.name).replace('_', '/', 2)  # Reconstruct path
            # This is a simplified approach - might need adjustment
            original_path = original_path.replace('_', '/')
            target_file = Path('/' + original_path)
            
            if target_file.exists():
                try:
                    shutil.copy2(backup_file, target_file)
                    restored += 1
                    print(f"Restored: {target_file.name}")
                except Exception as e:
                    print(f"Error restoring {target_file.name}: {e}")
    
    return restored > 0

def main():
    print("=== CS2 Font Replacer for Linux ===\n")
    
    # Find CS2 installation
    cs2_path = find_cs2_path()
    
    if not cs2_path:
        print("CS2 installation not found!")
        custom_path = input("Enter CS2 installation path manually (or press Enter to exit): ").strip()
        if custom_path:
            cs2_path = Path(custom_path)
            if not cs2_path.exists():
                print("Invalid path!")
                return
        else:
            return
    
    print(f"Found CS2 at: {cs2_path}\n")
    
    # Font directory (typical location)
    font_dir = cs2_path / "game/csgo/panorama/fonts"
    panorama_dir = cs2_path / "game/csgo/panorama"
    
    if not font_dir.exists():
        print(f"Font directory not found at: {font_dir}")
        print("The font location may have changed. Please check manually.")
        return
    
    backup_dir = cs2_path / "font_backup"
    
    # Menu
    print("Options:")
    print("1. Replace fonts")
    print("2. Adjust font sizes (pixelsize)")
    print("3. Replace fonts and adjust sizes")
    print("4. Scan for style files (diagnostic)")
    print("5. Restore original fonts and sizes")
    print("6. Exit")
    
    choice = input("\nEnter choice (1-6): ").strip()
    
    if choice == "1":
        print("\nNote: This will backup your original fonts first.")
        font_path = input("Enter path to replacement font file (.ttf or .otf): ").strip()
        
        if not font_path:
            print("No font specified!")
            return
        
        font_path = os.path.expanduser(font_path)
        
        print("\n--- Backing up original fonts ---")
        backup_fonts(font_dir, backup_dir)
        
        print("\n--- Replacing fonts ---")
        if replace_fonts(font_dir, font_path):
            print("\n✓ Fonts replaced successfully!")
            print("Restart CS2 to see changes.")
        else:
            print("\n✗ Font replacement failed!")
    
    elif choice == "2":
        scale = input("Enter font size scale factor (e.g., 1.2 for 20% larger, 0.8 for 20% smaller): ").strip()
        try:
            scale_factor = float(scale)
            if scale_factor <= 0:
                print("Scale factor must be positive!")
                return
        except ValueError:
            print("Invalid scale factor!")
            return
        
        print("\n--- Finding style files ---")
        style_files = find_style_files(panorama_dir)
        
        if not style_files:
            print("No style files found!")
            return
        
        print(f"Found {len(style_files)} style files")
        
        print("\n--- Backing up style files ---")
        backup_style_files(style_files, backup_dir)
        
        print("\n--- Adjusting font sizes ---")
        modified = adjust_font_sizes(style_files, scale_factor)
        
        if modified > 0:
            print(f"\n✓ Modified {modified} files!")
            print("Restart CS2 to see changes.")
        else:
            print("\n✗ No pixelsize values found to modify!")
    
    elif choice == "3":
        print("\nNote: This will backup your original fonts and style files.")
        font_path = input("Enter path to replacement font file (.ttf or .otf): ").strip()
        
        if not font_path:
            print("No font specified!")
            return
        
        font_path = os.path.expanduser(font_path)
        
        scale = input("Enter font size scale factor (e.g., 1.2 for 20% larger, 0.8 for 20% smaller): ").strip()
        try:
            scale_factor = float(scale)
            if scale_factor <= 0:
                print("Scale factor must be positive!")
                return
        except ValueError:
            print("Invalid scale factor!")
            return
        
        print("\n--- Backing up original fonts ---")
        backup_fonts(font_dir, backup_dir)
        
        print("\n--- Finding style files ---")
        style_files = find_style_files(panorama_dir)
        
        if style_files:
            print(f"Found {len(style_files)} style files")
            print("\n--- Backing up style files ---")
            backup_style_files(style_files, backup_dir)
        
        print("\n--- Replacing fonts ---")
        fonts_success = replace_fonts(font_dir, font_path)
        
        if style_files:
            print("\n--- Adjusting font sizes ---")
            modified = adjust_font_sizes(style_files, scale_factor)
            print(f"Modified {modified} files")
        
        if fonts_success:
            print("\n✓ Fonts replaced and sizes adjusted!")
            print("Restart CS2 to see changes.")
        else:
            print("\n✗ Font replacement failed!")
    
    elif choice == "4":
        print("\n--- Scanning for style files ---")
        style_files = find_style_files(panorama_dir)
        
        if style_files:
            print(f"\nTotal style files found: {len(style_files)}")
            print("\nFirst 20 files:")
            for f in style_files[:20]:
                rel_path = f.relative_to(cs2_path)
                print(f"  - {rel_path}")
            if len(style_files) > 20:
                print(f"  ... and {len(style_files) - 20} more")
        
        print("\n--- Checking for VPK archives ---")
        vpk_files = find_vpk_files(cs2_path)
        if vpk_files:
            print(f"Found {len(vpk_files)} VPK files:")
            for vpk in vpk_files[:10]:
                print(f"  - {vpk.name}")
            print("\nNote: Style files may be packed inside VPK archives.")
            print("You may need GCFScape or vpk.exe to extract and modify them.")
        else:
            print("No VPK files found.")
    
    elif choice == "5":
        print("\n--- Restoring original fonts ---")
        fonts_restored = restore_fonts(font_dir, backup_dir)
        
        print("\n--- Restoring style files ---")
        style_restored = restore_style_files(panorama_dir, backup_dir)
        
        if fonts_restored or style_restored:
            print("\n✓ Restoration complete!")
            print("Restart CS2 to see changes.")
        else:
            print("\n✗ Restoration failed!")
    
    elif choice == "6":
        print("Exiting...")
    
    else:
        print("Invalid choice!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        sys.exit(0)
