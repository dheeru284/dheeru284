import * as React from "react";

import { cn } from "@/lib/utils";

function Alert({
  className,
  tone = "info",
  ...props
}: React.ComponentProps<"div"> & { tone?: "info" | "error" | "success" | "warning" }) {
  const tones = {
    info: "border-border bg-muted text-foreground",
    error: "border-destructive/40 bg-destructive/10 text-foreground",
    success: "border-success/40 bg-success/10 text-foreground",
    warning: "border-warning/60 bg-warning/15 text-foreground",
  };
  return <div role="status" className={cn("rounded-md border px-3 py-2 text-sm", tones[tone], className)} {...props} />;
}

export { Alert };
