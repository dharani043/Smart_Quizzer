import os

# Files to remove (unused files we created)
unused_files = [
    'check_models.py',
    'test_gemini.py',
]

for file in unused_files:
    if os.path.exists(file):
        os.remove(file)
        print(f"Removed {file}")
    else:
        print(f"{file} not found")