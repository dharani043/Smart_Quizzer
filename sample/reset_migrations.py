import os
import glob

# Remove failed migration files
migration_files = glob.glob('base/migrations/0015_*.py')
for file in migration_files:
    if os.path.exists(file):
        os.remove(file)
        print(f"Removed {file}")

print("Migration files cleaned up. Now run:")
print("python manage.py makemigrations")
print("python manage.py migrate")