import { createBrowserRouter, Navigate } from "react-router";
import { RequireAuth } from "./components/require-auth";
import { ComponentShowcase } from "./components/component-showcase";
import { Dashboard } from "./pages/dashboard";
import { Home } from "./pages/home";
import { Recap } from "./pages/recap";
import { Simulation } from "./pages/simulation";
import { SignIn } from "./pages/sign-in";
import { Transactions } from "./pages/transactions";

export const router = createBrowserRouter([
  { path: "/", element: <Navigate to="/sign-in" replace /> },
  { path: "/sign-in", element: <SignIn /> },
  {
    path: "/dashboard",
    element: (
      <RequireAuth>
        <Dashboard />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <Home /> },
      { path: "transactions", element: <Transactions /> },
      { path: "simulation", element: <Simulation /> },
      { path: "recap", element: <Recap /> },
    ],
  },
  { path: "/components", element: <ComponentShowcase /> },
  { path: "*", element: <Navigate to="/" replace /> },
]);
