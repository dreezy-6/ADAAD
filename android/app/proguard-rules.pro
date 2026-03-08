# ADAAD ProGuard rules

# Keep governance engine classes — reflection used for rule dispatch
-keep class com.innovativeai.adaad.governance.** { *; }
-keep class com.innovativeai.adaad.data.** { *; }

# BouncyCastle — cryptographic signing
-keep class org.bouncycastle.** { *; }
-dontwarn org.bouncycastle.**

# Retrofit + OkHttp
-dontwarn okhttp3.**
-dontwarn okio.**
-keep class retrofit2.** { *; }
-keepattributes Signature
-keepattributes Exceptions

# Room — database entities
-keep class * extends androidx.room.RoomDatabase
-keep @androidx.room.Entity class *
-keep @androidx.room.Dao class *

# Kotlin coroutines
-keepnames class kotlinx.coroutines.internal.MainDispatcherFactory {}
-keepnames class kotlinx.coroutines.CoroutineExceptionHandler {}

# GSON — JSON serialisation for governance API payloads
-keep class com.google.gson.** { *; }
-keep class * implements com.google.gson.TypeAdapterFactory
-keepattributes *Annotation*
