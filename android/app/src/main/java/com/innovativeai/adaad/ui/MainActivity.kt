package com.innovativeai.adaad.ui

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.*
import com.innovativeai.adaad.ADAadApplication
import com.innovativeai.adaad.ui.navigation.ADAadNavGraph
import com.innovativeai.adaad.ui.screens.BootErrorScreen
import com.innovativeai.adaad.ui.theme.ADAadTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        setContent {
            ADAadTheme {
                val app = ADAadApplication.instance
                if (app.isBootHealthy()) {
                    ADAadNavGraph()
                } else {
                    BootErrorScreen(
                        errorMessage = app.bootError ?: "Unknown error",
                        onRetry      = { recreate() }
                    )
                }
            }
        }
    }
}
