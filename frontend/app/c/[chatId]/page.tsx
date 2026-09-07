import { redirect } from "next/navigation";

export default async function LegacyConversationPage({
  params,
}: {
  params: Promise<{ chatId: string }>;
}) {
  const { chatId } = await params;
  redirect(`/project/c/${chatId}`);
}
