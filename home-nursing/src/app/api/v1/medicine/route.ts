import { AppError } from "@/lib/errors";
import { errorResponse } from "@/lib/api";

/** Future phase boundary. Medicine delivery is not implemented and requires separate regulatory review. */
export async function GET() {
  return errorResponse(new AppError("FEATURE_DISABLED", "Medicine delivery is not available."));
}
export const POST = GET;
