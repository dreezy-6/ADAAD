package com.innovativeai.adaad.governance

import android.content.Context
import android.util.Log
import java.io.File
import java.security.MessageDigest
import java.time.Instant
import org.json.JSONArray
import org.json.JSONObject

/**
 * GovernanceLedger — local append-only ledger for Android.
 *
 * Mirrors LineageLedgerV2: every governance event is appended with a
 * cumulative SHA-256 chain hash. The ledger is replay-verifiable: any
 * replay of the event sequence must produce the same chain hash.
 *
 * On Android the ledger covers:
 *   - GovernanceGate evaluations (proposal → verdict)
 *   - Epoch completions
 *   - Federation sync events
 *   - Constitution load/reload events
 *   - Boot validation events
 */
class GovernanceLedger(private val context: Context) {

    companion object {
        private const val TAG = "GovernanceLedger"
        private const val LEDGER_FILE = "governance_ledger.jsonl"
        private const val INTEGRITY_FILE = "ledger_integrity.json"
    }

    private val ledgerFile = File(context.filesDir, LEDGER_FILE)
    private val integrityFile = File(context.filesDir, INTEGRITY_FILE)

    var epochCount: Int = 0
        private set
    var eventCount: Int = 0
        private set
    var chainHash: String = "0".repeat(64)
        private set

    data class LedgerEvent(
        val eventId: String,
        val eventType: String,
        val payload: Map<String, Any>,
        val timestamp: Instant,
        val prevHash: String,
        val eventHash: String
    )

    fun verifyIntegrity() {
        if (!ledgerFile.exists()) {
            Log.i(TAG, "Ledger not found — initialising new ledger")
            initLedger()
            return
        }

        var runningHash = "0".repeat(64)
        var count = 0
        var epochs = 0

        ledgerFile.forEachLine { line ->
            if (line.isBlank()) return@forEachLine
            val obj = JSONObject(line)
            val prevHash = obj.getString("prev_hash")
            val storedHash = obj.getString("event_hash")

            if (prevHash != runningHash) {
                throw LedgerIntegrityException(
                    "Ledger chain break at event ${obj.getString("event_id")}: " +
                    "expected prev_hash=$runningHash got=$prevHash"
                )
            }

            val recomputedHash = computeEventHash(obj)
            if (recomputedHash != storedHash) {
                throw LedgerIntegrityException(
                    "Ledger hash mismatch at event ${obj.getString("event_id")}"
                )
            }

            runningHash = storedHash
            count++
            if (obj.getString("event_type").startsWith("epoch_")) epochs++
        }

        chainHash  = runningHash
        eventCount = count
        epochCount = epochs
        Log.i(TAG, "Ledger verified — $count events, $epochs epochs, chain=$chainHash")
    }

    fun append(eventType: String, payload: Map<String, Any>): LedgerEvent {
        val eventId = "${eventType}_${System.currentTimeMillis()}"
        val obj = JSONObject().apply {
            put("event_id", eventId)
            put("event_type", eventType)
            put("timestamp", Instant.now().toString())
            put("prev_hash", chainHash)
            put("payload", JSONObject(payload))
        }
        val eventHash = computeEventHash(obj)
        obj.put("event_hash", eventHash)

        ledgerFile.appendText(obj.toString() + "\n")
        chainHash = eventHash
        eventCount++
        if (eventType.startsWith("epoch_")) epochCount++

        Log.d(TAG, "Ledger append: $eventType → $eventHash")

        return LedgerEvent(
            eventId   = eventId,
            eventType = eventType,
            payload   = payload,
            timestamp = Instant.now(),
            prevHash  = chainHash,
            eventHash = eventHash
        )
    }

    fun getRecentEvents(limit: Int = 50): List<JSONObject> {
        if (!ledgerFile.exists()) return emptyList()
        val lines = ledgerFile.readLines().filter { it.isNotBlank() }
        return lines.takeLast(limit).map { JSONObject(it) }
    }

    private fun initLedger() {
        ledgerFile.createNewFile()
        append("ledger_init", mapOf("version" to "3.0.0", "device" to "android"))
    }

    private fun computeEventHash(obj: JSONObject): String {
        val canonical = "${obj.getString("event_id")}:" +
            "${obj.getString("event_type")}:" +
            "${obj.getString("timestamp")}:" +
            "${obj.getString("prev_hash")}:" +
            obj.getJSONObject("payload").toString()
        val digest = MessageDigest.getInstance("SHA-256")
        return digest.digest(canonical.toByteArray())
            .joinToString("") { "%02x".format(it) }
    }
}

class LedgerIntegrityException(message: String) : Exception(message)
