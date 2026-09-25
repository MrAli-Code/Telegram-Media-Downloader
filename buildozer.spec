[app]
# اسکلت پیکربندی نسخه همراه اندروید (Companion).
# نیازمند Android SDK/NDK و python-for-android است.
title = Telegram Downloader
package.name = tdl
package.domain = org.example
source.dir = .
source.include_exts = py
version = 1.0.1
requirements = python3,telethon,cryptography,PySocks
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,ACCESS_NETWORK_STATE,FOREGROUND_SERVICE,POST_NOTIFICATIONS
android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a,armeabi-v7a

[buildozer]
log_level = 2
warn_on_root = 0