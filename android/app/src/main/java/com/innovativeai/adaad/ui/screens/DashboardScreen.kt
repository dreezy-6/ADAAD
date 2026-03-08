package com.innovativeai.adaad.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.navigation.NavHostController
import com.innovativeai.adaad.ui.navigation.Screen
import com.innovativeai.adaad.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardScreen(navController: NavHostController) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("ADAAD", fontWeight = FontWeight.Bold, fontSize = 20.sp)
                        Text("Constitutional Governance", fontSize = 12.sp,
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f))
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.primary,
                    titleContentColor = Color.White
                ),
                actions = {
                    IconButton(onClick = { navController.navigate(Screen.Settings.route) }) {
                        Icon(Icons.Default.Settings, contentDescription = "Settings", tint = Color.White)
                    }
                }
            )
        },
        bottomBar = { ADAadBottomBar(navController) }
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
            contentPadding = PaddingValues(vertical = 16.dp)
        ) {
            // Constitution health banner
            item { ConstitutionHealthBanner() }

            // Stats row
            item {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    StatCard(Modifier.weight(1f), "Epochs", "142", Icons.Default.Loop, Green)
                    StatCard(Modifier.weight(1f), "Rules Active", "13", Icons.Default.Gavel, Blue)
                    StatCard(Modifier.weight(1f), "Chain Hash", "a3f9…b2c1", Icons.Default.Link, Teal)
                }
            }

            // Recent governance activity
            item {
                Text("Recent Activity",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.padding(top = 8.dp)
                )
            }
            items(sampleActivity) { event ->
                GovernanceEventCard(event, navController)
            }

            // Pending proposals
            item {
                Text("Pending Review",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold
                )
            }
            items(sampleProposals) { proposal ->
                PendingProposalCard(proposal, navController)
            }
        }
    }
}

@Composable
private fun ConstitutionHealthBanner() {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = Green.copy(alpha = 0.12f)),
        shape = RoundedCornerShape(12.dp)
    ) {
        Row(
            modifier = Modifier.padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Icon(Icons.Default.VerifiedUser, contentDescription = null, tint = Green)
            Column {
                Text("Constitution v0.3.0 — HEALTHY",
                    fontWeight = FontWeight.Bold, color = Green, fontSize = 14.sp)
                Text("13 rules active · All Tier 0 gates green · Ledger verified",
                    fontSize = 12.sp, color = Green.copy(alpha = 0.8f))
            }
        }
    }
}

@Composable
private fun StatCard(
    modifier: Modifier = Modifier,
    label: String,
    value: String,
    icon: ImageVector,
    color: Color
) {
    Card(
        modifier = modifier,
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = color.copy(alpha = 0.08f))
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Icon(icon, contentDescription = label, tint = color, modifier = Modifier.size(22.dp))
            Spacer(Modifier.height(4.dp))
            Text(value, fontWeight = FontWeight.Bold, fontSize = 16.sp, color = color)
            Text(label, fontSize = 10.sp, color = MaterialTheme.colorScheme.onSurface.copy(0.6f))
        }
    }
}

data class GovernanceEvent(val type: String, val description: String, val time: String, val passed: Boolean)
data class PendingProposal(val id: String, val file: String, val authority: String, val agentId: String)

val sampleActivity = listOf(
    GovernanceEvent("epoch_complete", "Epoch #142 completed — 3 mutations merged", "2m ago", true),
    GovernanceEvent("gate_pass", "Proposal P-4412: ast_validity PASS", "8m ago", true),
    GovernanceEvent("gate_fail", "Proposal P-4411: no_banned_tokens FAIL", "15m ago", false),
    GovernanceEvent("federation_sync", "Federation sync with origin repo complete", "1h ago", true),
    GovernanceEvent("ledger_verify", "Ledger integrity verified — 142 epochs", "3h ago", true),
)

val sampleProposals = listOf(
    PendingProposal("P-4413", "runtime/governance/review_pressure.py", "governor_review", "ArchitectAgent"),
    PendingProposal("P-4414", "docs/ROADMAP.md", "low_impact", "DocAgent"),
)

@Composable
private fun GovernanceEventCard(event: GovernanceEvent, navController: NavHostController) {
    val color = if (event.passed) Green else Red
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(10.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
    ) {
        Row(
            modifier = Modifier.padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Box(
                Modifier.size(8.dp).clip(RoundedCornerShape(4.dp)).background(color)
            )
            Column(Modifier.weight(1f)) {
                Text(event.description, fontSize = 13.sp, fontWeight = FontWeight.Medium)
                Text(event.type, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurface.copy(0.5f))
            }
            Text(event.time, fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurface.copy(0.4f))
        }
    }
}

@Composable
private fun PendingProposalCard(proposal: PendingProposal, navController: NavHostController) {
    Card(
        modifier = Modifier.fillMaxWidth().clickable {
            navController.navigate(Screen.ProposalReview.withId(proposal.id))
        },
        shape = RoundedCornerShape(10.dp),
        colors = CardDefaults.cardColors(containerColor = Amber.copy(alpha = 0.08f))
    ) {
        Row(
            modifier = Modifier.padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Icon(Icons.Default.RateReview, contentDescription = null, tint = Amber, modifier = Modifier.size(20.dp))
            Column(Modifier.weight(1f)) {
                Text(proposal.file, fontSize = 13.sp, fontWeight = FontWeight.Medium)
                Text("${proposal.agentId} · ${proposal.authority}", fontSize = 11.sp,
                    color = MaterialTheme.colorScheme.onSurface.copy(0.6f))
            }
            Icon(Icons.Default.ChevronRight, contentDescription = null,
                tint = Amber, modifier = Modifier.size(18.dp))
        }
    }
}

@Composable
fun ADAadBottomBar(navController: NavHostController) {
    NavigationBar {
        NavigationBarItem(
            selected = true,
            onClick = { navController.navigate(Screen.Dashboard.route) },
            icon = { Icon(Icons.Default.Dashboard, contentDescription = "Dashboard") },
            label = { Text("Dashboard") }
        )
        NavigationBarItem(
            selected = false,
            onClick = { navController.navigate(Screen.Proposals.route) },
            icon = { Icon(Icons.Default.Assignment, contentDescription = "Proposals") },
            label = { Text("Proposals") }
        )
        NavigationBarItem(
            selected = false,
            onClick = { navController.navigate(Screen.Ledger.route) },
            icon = { Icon(Icons.Default.BookmarkBorder, contentDescription = "Ledger") },
            label = { Text("Ledger") }
        )
        NavigationBarItem(
            selected = false,
            onClick = { navController.navigate(Screen.Constitution.route) },
            icon = { Icon(Icons.Default.Gavel, contentDescription = "Constitution") },
            label = { Text("Rules") }
        )
    }
}
