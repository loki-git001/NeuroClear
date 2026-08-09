import { redirect } from "next/navigation";

/**
 * Root index route — immediately redirects to /screening.
 * This ensures users always land on the primary application view.
 */
export default function Home() {
  redirect("/screening");
}
