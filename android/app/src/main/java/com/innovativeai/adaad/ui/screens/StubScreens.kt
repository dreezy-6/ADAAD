package com.innovativeai.adaad.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.navigation.NavHostController

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EpochsScreen(navController: NavHostController) = SimpleScreen("Epochs", "Epoch history and replay proofs", navController)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EpochDetailScreen(epochId: String, navController: NavHostController) = SimpleScreen("Epoch $epochId", "Constitutional rule verdicts and evidence bundle", navController)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ProposalsScreen(navController: NavHostController) = SimpleScreen("Proposals", "Pending and historical mutation proposals", navController)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ProposalReviewScreen(proposalId: String, navController: NavHostController) = SimpleScreen("Review $proposalId", "Approve or reject governance proposal", navController)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LedgerScreen(navController: NavHostController) = SimpleScreen("Governance Ledger", "Append-only chain-hashed event ledger", navController)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FederationScreen(navController: NavHostController) = SimpleScreen("Federation", "Multi-repo federation status and HMAC key health", navController)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(navController: NavHostController) = SimpleScreen("Settings", "API endpoint, signing keys, environment", navController)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OnboardingScreen(navController: NavHostController) = SimpleScreen("Welcome to ADAAD", "Set up your governance workspace in minutes", navController)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BootErrorScreen(errorMessage: String, onRetry: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().padding(32.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Icon(Icons.Default.Error, contentDescription = null, tint = MaterialTheme.colorScheme.error,
            modifier = Modifier.size(64.dp))
        Spacer(Modifier.height(16.dp))
        Text("Boot Failure", fontWeight = FontWeight.Bold, fontSize = 22.sp, color = MaterialTheme.colorScheme.error)
        Spacer(Modifier.height(8.dp))
        Text("ADAAD failed its boot sequence (fail-closed):", fontSize = 14.sp)
        Spacer(Modifier.height(8.dp))
        Surface(color = MaterialTheme.colorScheme.errorContainer, shape = MaterialTheme.shapes.medium) {
            Text(errorMessage, modifier = Modifier.padding(12.dp), fontSize = 12.sp,
                color = MaterialTheme.colorScheme.onErrorContainer)
        }
        Spacer(Modifier.height(24.dp))
        Button(onClick = onRetry) { Text("Retry") }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SimpleScreen(title: String, subtitle: String, navController: NavHostController) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(title, fontWeight = FontWeight.Bold, fontSize = 18.sp)
                        Text(subtitle, fontSize = 11.sp, color = Color.White.copy(0.7f))
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
        },
        bottomBar = { ADAadBottomBar(navController) }
    ) { padding ->
        Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
            Text("$title — full implementation in v3.1.0",
                color = MaterialTheme.colorScheme.onSurface.copy(0.4f), fontSize = 13.sp)
        }
    }
}
