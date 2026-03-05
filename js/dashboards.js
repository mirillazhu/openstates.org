import AccountsOverview from "./account-overview";
import { addDataHookListener } from "./utils";

addDataHookListener("account-overview", "context", AccountsOverview);
