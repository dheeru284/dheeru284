process.env.DATABASE_URL = process.env.TEST_DATABASE_URL ?? "postgresql://hn:hn@localhost:5432/homenursing_test";
(process.env as Record<string, string>).NODE_ENV = "test";
process.env.OTP_SECRET = "test-otp-secret-0123456789";
process.env.DEV_EXPOSE_OTP = "false";
