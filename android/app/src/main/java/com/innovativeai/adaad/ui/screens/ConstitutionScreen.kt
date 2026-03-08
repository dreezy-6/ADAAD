package com.innovativeai.adaad.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.navigation.NavHostController
import com.innovativeai.adaad.ui.theme.*

data class ConstitutionRule(
    val id: String,
    val name: String,
    val tier: Int,
    val description: String,
    val enforced: Boolean
)

private val constitutionRules = listOf(
    ConstitutionRule("ast_validity","AST Validity",0,"Mutation diff must be syntactically valid Python AST",true),
    ConstitutionRule("no_banned_tokens","No Banned Tokens",0,"Diff must not contain eval, exec, or shell injection primitives",true),
    ConstitutionRule("signature_required","Signature Required",0,"All proposals must carry a valid Ed25519 governance signature",true),
    ConstitutionRule("lineage_continuity","Lineage Continuity",0,"Proposal must chain to a verified previous epoch SHA-256 hash",true),
    ConstitutionRule("single_file_scope","Single File Scope",1,"Each mutation must target exactly one file",true),
    ConstitutionRule("resource_bounds","Resource Bounds",0,"Mutations must not exceed resource budget or claim execution authority",true),
    ConstitutionRule("entropy_budget_limit","Entropy Budget",1,"Entropy token consumption must not exceed 4096 per proposal",true),
    ConstitutionRule("complexity_delta","Complexity Delta",1,"Cyclomatic complexity delta must not exceed 50 per mutation",true),
    ConstitutionRule("reviewer_calibration","Reviewer Calibration",2,"Advisory: reviewer reputation signal for governance pressure adjustment",true),
    ConstitutionRule("revenue_credit_floor","Revenue Credit Floor",2,"Advisory: economic fitness telemetry for Darwinian budget competition",true),
    ConstitutionRule("deployment_authority","Deployment Authority Tier",0,"Authority level must be low_impact, governor_review, or high_impact",true),
    ConstitutionRule("federation_dual_gate","Federation Dual Gate",0,"Federated mutations require GovernanceGate approval in both repos",true),
    ConstitutionRule("federation_hmac_required","Federation HMAC Required",0,"Federation-enabled nodes must present valid HMAC key at boot",true),
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ConstitutionScreen(navController: NavHostController) {
    var selectedTier by remember { mutableIntStateOf(-1) } // -1 = all

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("Constitution", fontWeight = FontWeight.Bold, fontSize = 20.sp)
                        Text("v0.3.0 — 13 rules active", fontSize = 12.sp, color = Color.White.copy(0.7f))
                    }
                },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back", tint = Color.White)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.primary,
                    titleContentColor = Color.White
                )
            )
        }
    ) { padding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding).padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
            contentPadding = PaddingValues(vertical = 16.dp)
        ) {
            item {
                // Tier filter chips
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf(-1 to "All", 0 to "Tier 0", 1 to "Tier 1", 2 to "Tier 2").forEach { (t, label) ->
                        FilterChip(
                            selected = selectedTier == t,
                            onClick  = { selectedTier = t },
                            label    = { Text(label, fontSize = 12.sp) },
                            colors   = FilterChipDefaults.filterChipColors(
                                selectedContainerColor = tierColor(t).copy(0.2f)
                            )
                        )
                    }
                }
            }

            items(constitutionRules.filter { selectedTier == -1 || it.tier == selectedTier }) { rule ->
                RuleCard(rule)
            }
        }
    }
}

@Composable
private fun RuleCard(rule: ConstitutionRule) {
    val color = tierColor(rule.tier)
    val tierLabel = when (rule.tier) {
        0    -> "BLOCKING"
        1    -> "POST-APPROVAL"
        else -> "ADVISORY"
    }

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
    ) {
        Row(modifier = Modifier.padding(14.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Box(
                Modifier.width(4.dp).height(48.dp)
                    .background(color, RoundedCornerShape(2.dp))
            )
            Column(Modifier.weight(1f)) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(rule.name, fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
                    Surface(
                        shape = RoundedCornerShape(4.dp),
                        color = color.copy(0.15f)
                    ) {
                        Text(tierLabel, fontSize = 10.sp, color = color,
                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                            fontWeight = FontWeight.Bold)
                    }
                }
                Spacer(Modifier.height(4.dp))
                Text(rule.description, fontSize = 12.sp,
                    color = MaterialTheme.colorScheme.onSurface.copy(0.65f))
                Spacer(Modifier.height(4.dp))
                Text(rule.id, fontSize = 11.sp, color = color.copy(0.7f), fontWeight = FontWeight.Medium)
            }
        }
    }
}

private fun tierColor(tier: Int): Color = when (tier) {
    0    -> Red
    1    -> Amber
    else -> Green
}
