package com.innovativeai.adaad.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// ── InnovativeAI / ADAAD brand colours ─────────────────────────────────────
val Navy           = Color(0xFF0F2B4A)
val NavyVariant    = Color(0xFF1A3A5E)
val Blue           = Color(0xFF1565C0)
val Sky            = Color(0xFF1E88E5)
val Teal           = Color(0xFF00ACC1)
val TealVariant    = Color(0xFF00838F)
val Amber          = Color(0xFFF57F17)
val Red            = Color(0xFFC62828)
val Green          = Color(0xFF2E7D32)
val Silver         = Color(0xFFF4F6F9)
val MidGrey        = Color(0xFFE1E5EB)
val CharcoalGrey   = Color(0xFF37474F)
val OnDark         = Color(0xFFECF0F4)

private val LightColorScheme = lightColorScheme(
    primary          = Navy,
    onPrimary        = Color.White,
    primaryContainer = NavyVariant,
    secondary        = Teal,
    onSecondary      = Color.White,
    tertiary         = Amber,
    background       = Silver,
    surface          = Color.White,
    onSurface        = Color(0xFF0D1117),
    error            = Red,
    outline          = MidGrey,
)

private val DarkColorScheme = darkColorScheme(
    primary          = Sky,
    onPrimary        = Color(0xFF0D1117),
    primaryContainer = NavyVariant,
    secondary        = Teal,
    onSecondary      = Color(0xFF0D1117),
    tertiary         = Amber,
    background       = Color(0xFF0D1117),
    surface          = Color(0xFF161B22),
    onSurface        = OnDark,
    error            = Color(0xFFEF9A9A),
    outline          = CharcoalGrey,
)

@Composable
fun ADAadTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit
) {
    val colorScheme = if (darkTheme) DarkColorScheme else LightColorScheme

    MaterialTheme(
        colorScheme = colorScheme,
        typography  = Typography(),
        content     = content
    )
}
