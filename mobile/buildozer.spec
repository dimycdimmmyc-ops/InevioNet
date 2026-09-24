[app]
title = InevioNet Mobile
package.name = inevionet
package.domain = org.inevionet
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0.0
requirements = python3,kivy,requests
orientation = portrait
fullscreen = 0
permissions = INTERNET
android.permissions = INTERNET
android.api = 30
android.minapi = 21
android.archs = arm64-v8a, armeabi-v7a
android.entrypoint = org.kivy.android.PythonActivity
