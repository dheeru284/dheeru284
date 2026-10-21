import { route } from "@/lib/api";
import { cancelStay } from "@/lib/domain/accommodation";

export const POST = route({ permission: "accommodation.book" }, async ({ principal, params }) => cancelStay(principal!, params.id!));
