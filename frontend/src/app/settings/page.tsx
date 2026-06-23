import { getServerSession } from "@/lib/auth";
import { redirect } from "next/navigation";
import { Navbar } from "@/components/ui/navbar";
import { SettingsContent } from "@/components/settings/settings-content";

export default async function SettingsPage() {
  const session = await getServerSession();
  if (!session?.user?.id) {
    redirect("/");
  }
  return (
    <div className="min-h-screen">
      <Navbar />
      <SettingsContent userEmail={session.user?.email ?? ""} />
    </div>
  );
}
