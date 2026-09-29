# GitHub Release upload checklist

Repository name: `Rita-Desktop-Pet`

Tag: `v0.1.0-beta`

Release title: `Rita Desktop Pet v0.1.0 Beta`

Release body: use `RELEASE_NOTES_v0.1.0-beta.md`.

Asset:

```text
dist/Rita-Desktop-Pet-v0.1.0-beta-portable.zip
```

## GitHub web steps

1. On GitHub, create a new public repository named `Rita-Desktop-Pet` without
   initializing it with a README, license, or `.gitignore`.
2. Add that repository as this checkout's `origin`, then push `master` and the
   tag `v0.1.0-beta`.
3. Open the repository's **Releases** page and choose **Draft a new release**.
4. Select the existing tag `v0.1.0-beta`.
5. Enter `Rita Desktop Pet v0.1.0 Beta` as the release title.
6. Paste the contents of `RELEASE_NOTES_v0.1.0-beta.md` into the description.
7. Upload `dist/Rita-Desktop-Pet-v0.1.0-beta-portable.zip`.
8. Mark the release as a pre-release, review the public page, then click
   **Publish release**.

## Git commands after creating the empty repository

Replace `<account>` with the GitHub account or organization that owns the
repository:

```powershell
git remote add origin https://github.com/<account>/Rita-Desktop-Pet.git
git push -u origin master
git push origin v0.1.0-beta
```
