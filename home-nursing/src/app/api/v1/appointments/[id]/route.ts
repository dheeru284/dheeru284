import { route } from "@/lib/api";
import { getAppointmentFor } from "@/lib/domain/appointments";

export const GET = route({ permission: "authenticated" }, async ({ principal, params }) => getAppointmentFor(principal!, params.id!));
