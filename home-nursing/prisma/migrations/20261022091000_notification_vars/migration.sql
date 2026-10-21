-- AlterTable
ALTER TABLE "Notification" ADD COLUMN     "vars" JSONB;

-- AlterTable
ALTER TABLE "NotificationTemplate" ADD COLUMN     "subject" TEXT;

