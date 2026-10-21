import { route } from "@/lib/api";
import { createStayOrder } from "@/lib/domain/payments";

export const POST = route({ permission: "accommodation.book" }, async ({ principal, params }) => createStayOrder(principal!, params.id!));
