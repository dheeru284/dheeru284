import { route } from "@/lib/api";
import { partnerBookings } from "@/lib/domain/accommodation";

export const GET = route({ permission: "stay.partner" }, async ({ principal }) => partnerBookings(principal!));
