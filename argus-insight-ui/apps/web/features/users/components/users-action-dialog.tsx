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

function RequiredLabel({ children }: { children: React.ReactNode }) {
  return (
    <FormLabel>
      {children} <span className="text-destructive">*</span>
    </FormLabel>
  )
}

type UsersActionDialogProps = {
  currentRow?: User
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function UsersActionDialog({
  currentRow,
  open,
  onOpenChange,
}: UsersActionDialogProps) {
  const isEdit = !!currentRow
  const { refreshUsers } = useUsers()

  const form = useForm<UserForm>({
    resolver: zodResolver(formSchema),
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

  // Compute whether Save button should be enabled
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
