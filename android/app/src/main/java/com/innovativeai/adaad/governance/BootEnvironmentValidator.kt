package com.innovativeai.adaad.governance

import android.content.Context
import com.innovativeai.adaad.BuildConfig

/**
 * BootEnvironmentValidator — mirrors the server-side _validate_boot_environment().
 *
 * Called as the very first operation in ADAadApplication.onCreate().
 * Any failure raises an exception that surfaces as a boot error screen.
 * The app never silently starts with an invalid environment.
 *
 * Android environment mapping:
 *   BuildConfig.DEBUG=true + TIER=community  → "dev"
 *   BuildConfig.DEBUG=false + TIER=community → "prod"
 *   BuildConfig.DEBUG=false + TIER=developer → "staging"
 *   BuildConfig.DEBUG=false + TIER=enterprise→ "production"
 */
object BootEnvironmentValidator {

    private val VALID_ENVS = setOf("dev", "staging", "production", "prod")

    fun validate(context: Context) {
        val env = resolveEnv()

        if (env !in VALID_ENVS) {
            throw RuntimeException(
                "ADAAD boot failed: unknown environment '$env'. " +
                "Valid environments: ${VALID_ENVS.joinToString()}. " +
                "This is a fail-closed invariant — the app will not start."
            )
        }

        // In staging/production/prod: governance signing key must be present
        if (env in setOf("staging", "production", "prod")) {
            val prefs = context.getSharedPreferences("adaad_governance", Context.MODE_PRIVATE)
            val keyPresent = prefs.getString("governance_signing_key_id", null) != null
            if (!keyPresent) {
                throw RuntimeException(
                    "ADAAD boot failed: governance signing key material absent in $env. " +
                    "Set up your governance key before using ADAAD in $env mode. " +
                    "See: docs/runbooks/key_setup_android.md"
                )
            }
        }
    }

    fun resolveEnv(): String {
        return when {
            BuildConfig.DEBUG                     -> "dev"
            BuildConfig.TIER == "enterprise"      -> "production"
            BuildConfig.TIER == "developer"       -> "staging"
            else                                  -> "prod"
        }
    }
}
