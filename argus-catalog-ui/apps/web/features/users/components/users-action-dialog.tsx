/**
 * User Add/Edit Dialog component.
 *
 * A modal form dialog used for both creating new users and editing existing ones.
 * The dialog mode (add vs. edit) is determined by the presence of `currentRow`:
 *
 * - **Add mode** (currentRow is undefined): All fields are empty. Username and
 *   password are required. Uniqueness checks run on blur for username and email.
 * - **Edit mode** (currentRow is provided): Fields are pre-populated with the
 *   user's current data. Username is disabled (cannot be changed). Password
 *   fields are optional — leave blank to keep the existing password.
 *
 * Form validation uses Zod schema with multiple refinements:
 * 1. Password is required in add mode, optional in edit mode.
 * 2. Password must be at least 8 characters with at least one lowercase letter
 *    and one digit.
 * 3. Password and confirm password must match.
 *
 * On successful submission, the dialog calls the appropriate API function
 * (createUser or modifyUser) and refreshes the user list.
 */

"use client"

import { useCallback } from "react"
import { z } from "zod"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"

import { Button } from "@workspace/ui/components/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@workspace/ui/components/dialog"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@workspace/ui/components/form"
import { Input } from "@workspace/ui/components/input"
import { PasswordInput } from "@/components/password-input"
import { SelectDropdown } from "@/components/select-dropdown"
import { checkUserExists, createUser, modifyUser } from "../api"
import { roles } from "../data/data"
import { type User } from "../data/schema"
import { useUsers } from "./users-provider"

/**
 * Zod validation schema for the user add/edit form.
 *
 * Uses an `isEdit` flag to conditionally relax password requirements in edit mode.
 * Multiple `.refine()` calls enforce password complexity rules:
 * - Required in add mode (non-empty after trim).
 * - Minimum 8 characters.
 * - At least one lowercase letter.
 * - At least one digit.
 * - Must match confirmPassword.
 *
 * In edit mode, if the password field is left blank, all password validations
 * are skipped (the existing password is preserved on the backend).
 */
const formSchema = z
  .object({
    firstName: z.string().min(1, "First Name is required."),
    lastName: z.string().min(1, "Last Name is required."),
    username: z.string().min(1, "Username is required."),
    phoneNumber: z.string().optional().default(""),
    email: z.string().min(1, "Email is required.").email("Invalid email address."),
    password: z.string().transform((pwd) => pwd.trim()),
    role: z.string().min(1, "Role is required."),
    confirmPassword: z.string().transform((pwd) => pwd.trim()),
    /** Hidden flag indicating whether the form is in edit mode. */
    isEdit: z.boolean(),
  })
  .refine(
    (data) => {
      if (data.isEdit && !data.password) return true
      return data.password.length > 0
    },
    { message: "Password is required.", path: ["password"] }
  )
  .refine(
    ({ isEdit, password }) => {
      if (isEdit && !password) return true
      return password.length >= 8
    },
    {
      message: "Password must be at least 8 characters long.",
      path: ["password"],
    }
  )
  .refine(
    ({ isEdit, password }) => {
      if (isEdit && !password) return true
      return /[a-z]/.test(password)
    },
    {
      message: "Password must contain at least one lowercase letter.",
      path: ["password"],
    }
  )
  .refine(
    ({ isEdit, password }) => {
      if (isEdit && !password) return true
      return /\d/.test(password)
    },
    {
      message: "Password must contain at least one number.",
      path: ["password"],
    }
  )
  .refine(
    ({ isEdit, password, confirmPassword }) => {
      if (isEdit && !password) return true
      return password === confirmPassword
    },
    { message: "Passwords don't match.", path: ["confirmPassword"] }
  )
type UserForm = z.infer<typeof formSchema>

/**
 * Helper component that renders a form label with a red asterisk
 * to indicate the field is required.
 */
function RequiredLabel({ children }: { children: React.ReactNode }) {
  return (
    <FormLabel>
      {children} <span className="text-destructive">*</span>
    </FormLabel>
  )
}

type UsersActionDialogProps = {
  /** The user being edited, or undefined for adding a new user. */
  currentRow?: User
  /** Whether the dialog is open. */
  open: boolean
  /** Callback to open or close the dialog. */
  onOpenChange: (open: boolean) => void
}

export function UsersActionDialog({
  currentRow,
  open,
  onOpenChange,
}: UsersActionDialogProps) {
  const isEdit = !!currentRow
  const { refreshUsers } = useUsers()

  /**
   * Initialize the form with React Hook Form + Zod resolver.
   *
   * In edit mode, the form is pre-populated with the current user's data
   * (password fields start empty). In add mode, all fields start empty
   * with the default role set to "user".
   *
   * Validation runs on touched fields (`mode: "onTouched"`) to provide
   * immediate feedback without validating untouched fields.
   */
  const form = useForm<UserForm>({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    resolver: zodResolver(formSchema) as any,
    mode: "onTouched",
    defaultValues: isEdit
      ? {
          ...currentRow,
          password: "",
          confirmPassword: "",
          isEdit,
        }
      : {
          firstName: "",
          lastName: "",
          username: "",
          email: "",
          role: "user",
          phoneNumber: "",
          password: "",
          confirmPassword: "",
          isEdit,
        },
  })

  /**
   * Async blur handler for the username field.
   *
   * When the user tabs out of the username input (in add mode only),
   * this calls the backend to check if the username is already taken.
   * If it is, a form error is set on the username field.
   */
  const handleCheckUsername = useCallback(
    async (value: string) => {
      if (!value || isEdit) return
      try {
        const result = await checkUserExists({ username: value })
        if (result.username_exists) {
          form.setError("username", {
            type: "validate",
            message: "This username is already taken.",
          })
        }
      } catch {
        // ignore network errors for validation
      }
    },
    [isEdit, form]
  )

  /**
   * Async blur handler for the email field.
   *
   * Similar to username check — validates email uniqueness against the backend
   * when the user tabs out of the email input. Only runs in add mode.
   */
  const handleCheckEmail = useCallback(
    async (value: string) => {
      if (!value || isEdit) return
      try {
        const result = await checkUserExists({ email: value })
        if (result.email_exists) {
          form.setError("email", {
            type: "validate",
            message: "This email is already registered.",
          })
        }
      } catch {
        // ignore network errors for validation
      }
    },
    [isEdit, form]
  )

  /**
   * Form submission handler.
   *
   * In edit mode: calls `modifyUser()` with only the editable profile fields.
   * In add mode: calls `createUser()` with all fields including password.
   * The role value is mapped from lowercase ("admin") to title-case ("Admin")
   * to match the backend's RoleName enum.
   *
   * After a successful save, refreshes the user list and closes the dialog.
   */
  const onSubmit = async (values: UserForm) => {
    try {
      if (isEdit && currentRow) {
        await modifyUser(currentRow.id, {
          first_name: values.firstName,
          last_name: values.lastName,
          email: values.email,
          phone_number: values.phoneNumber,
        })
      } else {
        const roleMap: Record<string, "Admin" | "User"> = { admin: "Admin", user: "User" }
        await createUser({
          username: values.username,
          email: values.email,
          first_name: values.firstName,
          last_name: values.lastName,
          phone_number: values.phoneNumber,
          password: values.password,
          role: roleMap[values.role] || "User",
        })
      }
      await refreshUsers()
      form.reset()
      onOpenChange(false)
    } catch (err) {
      console.error("Failed to save user:", err)
    }
  }

  const isPasswordTouched = !!form.formState.dirtyFields.password

  /**
   * Compute whether the Save button should be enabled.
   *
   * The button is disabled when:
   * - Required fields are not filled in.
   * - There are any validation errors (from Zod or async checks).
   *
   * In edit mode, only firstName, lastName, and email are required.
   * In add mode, all fields including username, role, password, and
   * confirmPassword are required.
   */
  const watched = form.watch()
  const hasErrors = Object.keys(form.formState.errors).length > 0
  const requiredFilled = isEdit
    ? !!(watched.firstName && watched.lastName && watched.email)
    : !!(
        watched.firstName &&
        watched.lastName &&
        watched.username &&
        watched.email &&
        watched.role &&
        watched.password &&
        watched.confirmPassword
      )
  const isSaveDisabled = !requiredFilled || hasErrors

  return (
    <Dialog
      open={open}
      onOpenChange={(state) => {
        form.reset()
        onOpenChange(state)
      }}
    >
      <DialogContent className="sm:max-w-lg">
        <DialogHeader className="text-start">
          <DialogTitle>{isEdit ? "Edit User" : "Add New User"}</DialogTitle>
          <DialogDescription>
            {isEdit ? "Update the user here. " : "Create new user here. "}
            Click save when you&apos;re done.
          </DialogDescription>
        </DialogHeader>
        <div className="py-1">
          <Form {...form}>
            <form
              id="user-form"
              onSubmit={form.handleSubmit(onSubmit)}
              className="space-y-4"
            >
              {/* First Name and Last Name side by side */}
              <div className="grid grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="firstName"
                  render={({ field }) => (
                    <FormItem>
                      <RequiredLabel>First Name</RequiredLabel>
                      <FormControl>
                        <Input placeholder="John" autoComplete="off" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="lastName"
                  render={({ field }) => (
                    <FormItem>
                      <RequiredLabel>Last Name</RequiredLabel>
                      <FormControl>
                        <Input placeholder="Doe" autoComplete="off" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              {/* Username field — disabled in edit mode since it cannot be changed */}
              <FormField
                control={form.control}
                name="username"
                render={({ field }) => (
                  <FormItem>
                    <RequiredLabel>Username</RequiredLabel>
                    <FormControl>
                      <Input
                        placeholder="john_doe"
                        disabled={isEdit}
                        {...field}
                        onBlur={(e) => {
                          field.onBlur()
                          handleCheckUsername(e.target.value)
                        }}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Email field — with async uniqueness check on blur */}
              <FormField
                control={form.control}
                name="email"
                render={({ field }) => (
                  <FormItem>
                    <RequiredLabel>Email</RequiredLabel>
                    <FormControl>
                      <Input
                        placeholder="john.doe@gmail.com"
                        {...field}
                        onBlur={(e) => {
                          field.onBlur()
                          handleCheckEmail(e.target.value)
                        }}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Phone Number and Role side by side */}
              <div className="grid grid-cols-2 gap-4">
                <FormField
                  control={form.control}
                  name="phoneNumber"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Phone Number</FormLabel>
                      <FormControl>
                        <Input placeholder="+123456789" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="role"
                  render={({ field }) => (
                    <FormItem>
                      <RequiredLabel>Role</RequiredLabel>
                      <SelectDropdown
                        defaultValue={field.value}
                        onValueChange={field.onChange}
                        placeholder="Select a role"
                        className="w-full"
                        items={roles.map(({ label, value }) => ({ label, value }))}
                      />
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              {/* Password field — required in add mode, optional in edit mode */}
              <FormField
                control={form.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <RequiredLabel>Password</RequiredLabel>
                    <FormControl>
                      <PasswordInput placeholder="e.g., S3cur3P@ssw0rd" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              {/* Confirm Password — only enabled after the password field is touched */}
              <FormField
                control={form.control}
                name="confirmPassword"
                render={({ field }) => (
                  <FormItem>
                    <RequiredLabel>Confirm Password</RequiredLabel>
                    <FormControl>
                      <PasswordInput
                        disabled={!isPasswordTouched}
                        placeholder="e.g., S3cur3P@ssw0rd"
                        {...field}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </form>
          </Form>
        </div>
        <DialogFooter>
          <Button type="submit" form="user-form" disabled={isSaveDisabled}>
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
