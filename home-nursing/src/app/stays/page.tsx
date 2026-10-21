import { Suspense } from "react";
import { StaySearch } from "./StaySearch";
export default function Page() {
  return (
    <div className="space-y-4">
      <h1 className="h1">Stays near hospitals</h1>
      <p className="muted max-w-2xl">Furnished and serviced apartments for patients and families on short or long stays. Only verified listings are shown. Hospitals in this directory are listed for reference and are not necessarily partners.</p>
      <Suspense><StaySearch /></Suspense>
    </div>
  );
}
