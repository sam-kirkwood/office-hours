import { requireAdmin } from "@/lib/adminAuth";
import AdminNav from "@/components/AdminNav";

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await requireAdmin();

  return (
    <div className="flex h-screen flex-col bg-background">
      <AdminNav operatorEmail={user.email ?? ""} />
      {children}
    </div>
  );
}
