-- AlterTable
ALTER TABLE "AccommodationBooking" ADD COLUMN     "cancellationReason" TEXT;

-- AlterTable
ALTER TABLE "Appointment" ADD COLUMN     "rescheduledFromId" TEXT;

-- AlterTable
ALTER TABLE "Hospital" ADD COLUMN     "hasFormalPartnership" BOOLEAN NOT NULL DEFAULT false,
ADD COLUMN     "partnershipAgreementRef" TEXT;

-- AlterTable
ALTER TABLE "PropertyImage" ADD COLUMN     "createdAt" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
ADD COLUMN     "storageKey" TEXT,
ALTER COLUMN "url" DROP NOT NULL;

-- CreateIndex
CREATE UNIQUE INDEX "Appointment_rescheduledFromId_key" ON "Appointment"("rescheduledFromId");

