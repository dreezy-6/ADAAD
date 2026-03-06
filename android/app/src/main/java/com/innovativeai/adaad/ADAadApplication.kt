package com.innovativeai.adaad

import android.app.Application
import android.util.Log
import com.innovativeai.adaad.governance.ConstitutionEngine
import com.innovativeai.adaad.governance.GovernanceLedger
import com.innovativeai.adaad.governance.BootEnvironmentValidator

/**
 * ADAAD Application entry point.
 *
 * Boot sequence mirrors the server-side main() contract:
 *   1. Boot environment validation (fail-closed on invalid ADAAD_ENV)
 *   2. Constitution engine initialisation
 *   3. Ledger integrity check
 *   4. Federation transport init (if enabled)
 *
 * Any failure in steps 1–3 is fatal and surfaces as a boot error screen.
 * The app NEVER silently degrades governance enforcement.
 */
class ADAadApplication : Application() {

    companion object {
        private const val TAG = "ADAadApplication"
        lateinit var instance: ADAadApplication
            private set
    }

    // Governance components — initialised at boot, never null after onCreate
    lateinit var constitutionEngine: ConstitutionEngine
        private set
    lateinit var governanceLedger: GovernanceLedger
        private set

    var bootError: String? = null
        private set

    override fun onCreate() {
        super.onCreate()
        instance = this
        performBootSequence()
    }

    private fun performBootSequence() {
        try {
            Log.i(TAG, "ADAAD boot sequence starting — v${BuildConfig.ADAAD_VERSION}")

            // Step 1: Validate boot environment (fail-closed)
            BootEnvironmentValidator.validate(this)
            Log.i(TAG, "Boot environment validated")

            // Step 2: Constitution engine
            constitutionEngine = ConstitutionEngine(
                context         = this,
                constitutionVer = BuildConfig.CONSTITUTION_VERSION,
                tier            = BuildConfig.TIER
            )
            constitutionEngine.load()
            Log.i(TAG, "Constitution v${BuildConfig.CONSTITUTION_VERSION} loaded — ${constitutionEngine.ruleCount} rules active")

            // Step 3: Governance ledger integrity check
            governanceLedger = GovernanceLedger(this)
            governanceLedger.verifyIntegrity()
            Log.i(TAG, "Ledger integrity verified — epoch count: ${governanceLedger.epochCount}")

            Log.i(TAG, "ADAAD boot sequence complete")
        } catch (e: Exception) {
            bootError = e.message ?: "Unknown boot failure"
            Log.e(TAG, "ADAAD boot sequence FAILED (fail-closed): $bootError", e)
            // Do NOT crash — let MainActivity render the boot error screen
            // so the user gets an actionable error rather than a force-close dialog
        }
    }

    fun isBootHealthy() = bootError == null
}
