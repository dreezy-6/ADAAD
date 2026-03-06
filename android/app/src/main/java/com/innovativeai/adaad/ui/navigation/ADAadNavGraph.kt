package com.innovativeai.adaad.ui.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.innovativeai.adaad.ui.screens.*

sealed class Screen(val route: String) {
    object Dashboard      : Screen("dashboard")
    object Epochs         : Screen("epochs")
    object EpochDetail    : Screen("epochs/{epochId}") {
        fun withId(id: String) = "epochs/$id"
    }
    object Proposals      : Screen("proposals")
    object ProposalReview : Screen("proposals/{proposalId}") {
        fun withId(id: String) = "proposals/$id"
    }
    object Constitution   : Screen("constitution")
    object Ledger         : Screen("ledger")
    object Federation     : Screen("federation")
    object Settings       : Screen("settings")
    object Onboarding     : Screen("onboarding")
}

@Composable
fun ADAadNavGraph(
    navController: NavHostController = rememberNavController()
) {
    NavHost(
        navController   = navController,
        startDestination = Screen.Dashboard.route
    ) {
        composable(Screen.Dashboard.route) {
            DashboardScreen(navController = navController)
        }
        composable(Screen.Epochs.route) {
            EpochsScreen(navController = navController)
        }
        composable(
            route     = Screen.EpochDetail.route,
            arguments = listOf(navArgument("epochId") { type = NavType.StringType })
        ) { backStack ->
            EpochDetailScreen(
                epochId       = backStack.arguments?.getString("epochId") ?: "",
                navController = navController
            )
        }
        composable(Screen.Proposals.route) {
            ProposalsScreen(navController = navController)
        }
        composable(
            route     = Screen.ProposalReview.route,
            arguments = listOf(navArgument("proposalId") { type = NavType.StringType })
        ) { backStack ->
            ProposalReviewScreen(
                proposalId    = backStack.arguments?.getString("proposalId") ?: "",
                navController = navController
            )
        }
        composable(Screen.Constitution.route) {
            ConstitutionScreen(navController = navController)
        }
        composable(Screen.Ledger.route) {
            LedgerScreen(navController = navController)
        }
        composable(Screen.Federation.route) {
            FederationScreen(navController = navController)
        }
        composable(Screen.Settings.route) {
            SettingsScreen(navController = navController)
        }
        composable(Screen.Onboarding.route) {
            OnboardingScreen(navController = navController)
        }
    }
}
