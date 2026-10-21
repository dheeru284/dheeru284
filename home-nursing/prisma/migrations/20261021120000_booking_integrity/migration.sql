-- Booking integrity enforced by the database, not just application code.
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- A nurse cannot hold two active appointments whose blocked windows (visit + travel buffer) overlap.
ALTER TABLE "Appointment" ADD CONSTRAINT appointment_no_nurse_overlap
  EXCLUDE USING gist ("nurseId" WITH =, tstzrange("blockStart", "blockEnd", '[)') WITH &&)
  WHERE (status NOT IN ('CANCELLED', 'RESCHEDULED', 'NO_SHOW', 'DRAFT'));

ALTER TABLE "Appointment" ADD CONSTRAINT appointment_time_order CHECK ("endAt" > "startAt" AND "blockEnd" > "blockStart");

-- A unit cannot have two active stays whose nights overlap (checkOut is exclusive).
ALTER TABLE "AccommodationBooking" ADD CONSTRAINT stay_no_unit_overlap
  EXCLUDE USING gist ("unitId" WITH =, daterange("checkIn", "checkOut", '[)') WITH &&)
  WHERE (status IN ('REQUESTED', 'CONFIRMED', 'CHECKED_IN'));

ALTER TABLE "AccommodationBooking" ADD CONSTRAINT stay_date_order CHECK ("checkOut" > "checkIn");
ALTER TABLE "Review" ADD CONSTRAINT review_rating_range CHECK (rating BETWEEN 1 AND 5);
