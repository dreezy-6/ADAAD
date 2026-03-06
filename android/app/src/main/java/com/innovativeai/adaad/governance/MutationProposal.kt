package com.innovativeai.adaad.governance

import java.time.Instant

/**
 * MutationProposal — mirrors the server-side governance envelope schema.
 *
 * Every proposal entering the GovernanceGate on Android must carry
 * all fields required by the constitutional rules. Missing or blank
 * required fields cause immediate Tier 0 failure.
 */
data class MutationProposal(
    val id: String,
    val diff: String,
    val affectedFiles: List<String>,
    val signature: String,
    val signerId: String,
    val prevEpochHash: String,
    val authorityLevel: String,          // low_impact | governor_review | high_impact
    val entropyTokens: Int,
    val complexityDelta: Int,
    val proposedAt: Instant = Instant.now(),
    val agentId: String = "",
    val bundleId: String = "",
    val epochId: String = "",

    // Federation fields
    val isFederated: Boolean = false,
    val originRepo: String = "",
    val originGateApproved: Boolean = false,
    val destinationGatePending: Boolean = false,
    val hmacPresent: Boolean = false,
    val hmacValid: Boolean = false,
    val federationKeyId: String = "",

    // Review tracking
    val reviewerId: String? = null,
    val reviewerDecision: String? = null,   // approved | rejected | escalated
    val reviewedAt: Instant? = null,
)

/**
 * GovernanceVerdict — the signed result of constitutional evaluation.
 */
data class GovernanceVerdict(
    val proposalId: String,
    val overallPassed: Boolean,
    val ruleResults: List<ConstitutionEngine.EvaluationResult>,
    val evidenceBundleHash: String,
    val evaluatedAt: Instant = Instant.now(),
    val constitutionVersion: String,
    val blockingFailure: String? = null      // null if passed; rule name if blocked
) {
    val failedRules get() = ruleResults.filter { !it.passed }
    val tier0Failures get() = ruleResults.filter { !it.passed && it.tier == 0 }
}
