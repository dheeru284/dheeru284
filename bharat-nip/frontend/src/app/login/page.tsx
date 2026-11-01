import { LoginForm } from "@/components/app/forms";
import { PageShell } from "@/components/app/page-shell";

export default function LoginPage() {
  return (
    <PageShell
      title="Sign in"
      description="Accounts are created by an administrator (uv run python -m app.cli create-user)."
    >
      <LoginForm />
    </PageShell>
  );
}
