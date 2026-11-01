import { Suspense } from "react";

import { SubmitForm } from "@/components/app/forms";
import { Loading, PageShell } from "@/components/app/page-shell";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/server-api";
import type { User } from "@/lib/types";

async function RequireUser() {
  await api<User>("/auth/me"); // redirects to /login when signed out
  return <SubmitForm />;
}

export default function SubmitPage() {
  return (
    <PageShell
      title="Submit material for fact-checking"
      description="The system extracts atomic claims, searches for evidence, proposes a classification, has an independent critic challenge it, and sends it to a human reviewer."
    >
      <Card>
        <CardContent>
          <Suspense fallback={<Loading />}>
            <RequireUser />
          </Suspense>
        </CardContent>
      </Card>
    </PageShell>
  );
}
