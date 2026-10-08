[app]

# (str) Title of your application
title = Surveyor Juel

# (str) Package name
package.name = surveyorjuel

# (str) Package domain (needed for android packaging)
package.domain = org.juel

# (list) Source files to include (let it empty to include all files)
source.include_exts = py,png,jpg,kv,atlas

# (list) List of inclusion & exclusion patterns in source files
source.include_patterns = assets/*,images/*.png

# (list) Source files to exclude (let it empty to not exclude anything)
source.exclude_exts = spec

# (list) List of directory to exclude
source.exclude_dirs = tests, bin, venv, .git, .github

# (list) Application requirements
# comma separated e.g. requirements = sqlite3,kivy
requirements = python3,kivy,reportlab,setuptools

# (str) Supported orientations
orientation = portrait

# (list) List of services
#services = 

#
# Android specific
#

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (list) Permissions
android.permissions = WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE

# (list) Target API, should be as high as possible.
android.api = 33

# (list) Minimum API your APK will support.
android.minapi = 21

# (str) Android SDK version to use
#android.sdk = 20

# (str) Android NDK version to use
#android.ndk = 25b

# (str) Android NDK home path
#android.ndk_path =

# (str) Android SDK home path
#android.sdk_path =

# (str) ANT home path
#android.ant_path =

# (bool) Use --private data storage (True) or --public storage (False)
android.private_storage = False

# (str) Supported architectures (arm64-v8a is mandatory for modern Google Play, armeabi-v7a for older devices)
android.architectures = arm64-v8a, armeabi-v7a

# (bool) Enable AndroidX support
android.androidx = True

[buildozer]

# (int) Log level (0 = error, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_root = 1

# (str) Path to build target
bin_dir = ./bin
