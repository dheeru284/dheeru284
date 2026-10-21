import { route } from "@/lib/api";
import { submitForVerification } from "@/lib/domain/credentials";

export const POST = route({ permission: "nurse.self" }, async ({ principal }) => submitForVerification(principal!));
