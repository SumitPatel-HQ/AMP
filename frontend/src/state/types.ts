import type { ApiErrorCode } from "../api/client";

export interface MissionSessionError {
  code: ApiErrorCode | "CLIENT_ERROR";
  message: string;
}
