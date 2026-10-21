import { route } from "@/lib/api";
import { authorizationQueue } from "@/lib/domain/appointments";

export const GET = route({ permission: "authorization.review" }, async ({ principal }) => authorizationQueue(principal!));
