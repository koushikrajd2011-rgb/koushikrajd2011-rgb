# Put it on GitHub

1. Sign in as `koushikrajd2011-rgb` and [create a repository](https://github.com/new)
   named **koushikrajd2011-rgb**. Make it **Public** and add a README.
2. Extract this download. Open the `git` folder and upload its
   **contents** into the repository root. Do not upload the outer folder or ZIP.
   Use **Add file → Upload files**, then commit the files to `main`.
3. Include `.github/workflows/refresh-cards.yml`. On macOS, press
   **Command–Shift–.** in Finder to reveal hidden folders. If the upload omits
   `.github`, use **Add file → Create new file**, enter that exact path, paste
   the bundled YAML file, and commit it.
4. In the repository's **Actions** tab, select **Refresh profile cards**, then
   **Run workflow**. The initial upload may already have started a run.
5. Open [your profile](https://github.com/koushikrajd2011-rgb). The cards appear
   once the root README and referenced images are committed. Future contribution
   updates run daily; you do not need to run Python on your computer.

The repository root should contain:

```text
README.md
render_cards.py
profile.json
requirements.txt
cards/
data/contributions.json
assets/fonts/
.github/workflows/refresh-cards.yml
```

The extra documentation and `cards-static/` preview are optional. The workflow
uses the built-in `GITHUB_TOKEN`; never upload a personal token. If the workflow
cannot push, check the job's error and repository Actions/branch permissions.

[GitHub's profile README requirements](https://docs.github.com/en/account-and-profile/how-tos/profile-customization/managing-your-profile-readme)
and [manual workflow instructions](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow).
