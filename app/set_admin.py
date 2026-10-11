import argparse

from app.database import get_supabase


def main() -> None:
    parser = argparse.ArgumentParser(description="Grant the admin role to a Supabase Auth user.")
    parser.add_argument("--user-id", required=True, help="UUID of the existing Supabase Auth user")
    args = parser.parse_args()

    admin_auth = get_supabase().auth.admin
    current_user = admin_auth.get_user_by_id(args.user_id).user
    if current_user is None:
        raise RuntimeError(f"Supabase user {args.user_id} was not found.")
    app_metadata = dict(current_user.app_metadata or {})
    app_metadata["role"] = "admin"
    result = admin_auth.update_user_by_id(args.user_id, {"app_metadata": app_metadata})
    if result.user is None:
        raise RuntimeError(f"Supabase did not return the updated user {args.user_id}.")
    print(f"Admin role granted to {result.user.email} ({result.user.id}).")


if __name__ == "__main__":
    main()
