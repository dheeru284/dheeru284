import { route } from "@/lib/api";
import { receiptFor } from "@/lib/domain/appointments";

export const GET = route({ permission: "authenticated" }, async ({ principal, params }) => receiptFor(principal!, params.id!));
