# PV247 - Helpful scripts for evaluation of homeworks

### Things to be aware of before running scripts - 

Script will **kill all the Chrome instances** - in other words - close all the chrome TABS, because it needs to connect to the chosen chrome Profile - in my case the Default profile and would not work properly without it. It runs in debug mode and uses Default profile as mentioned so it will use github session as I am logged in on github in this profile. Without that, you would have to provide passkey or SMS code (if you are using 2FA like me) to log in to the github to be able to enter PV247 site and clone repositories.

You can find out the name of the profile using `ls ~/.config/google-chrome/`.

When reviewing homework, you should put **H(h)odnotenie** or **H(h)odnoceni** or **E(e)valuation** inside pull request so the script will skip this repository when cloning / skip this repository when processing repositories.

<details>
  <summary>Click to see, what it should look like</summary>
  
![image](https://github.com/user-attachments/assets/6f92800d-0fad-4c50-9fa6-4efc99d96111)

![image](https://github.com/user-attachments/assets/6cc20f26-df2e-4844-b204-1414a8f1df8b)

</details>

If the script **wont start cloning repositories**, just terminate the current run of the script and **run it again**.

Some parts of the scripts use extended `sleep` or `wait` time. If u are runing the scripts on better machine and you feel like it takes longer then it should, you can lower down these and it will become quicker.

## How to run the scripts 

#### 0. Before running scripts

You will probably **need to adjust the chrome profile** at this section of the code inside `run_script.sh` at `--profile-directory...` if you want to use
other profile then Default or it is located inside other folder.

<details>
  <summary>Click to see, what you should change</summary>
  

  ```# Start Chrome in debug mode (if not already running)
if ! pgrep -f "chrome.*remote-debugging-port=9222" > /dev/null; then
    echo "🚀 Starting Chrome in debug mode..."
    google-chrome --remote-debugging-port=9222 \
                  --user-data-dir="/home/samuel/.config/google-chrome/" \
                  --profile-directory="Default" \
                  --disable-gpu 2>/dev/null &
```

</details>

####  1. Clone the repository  
 ```git clone git@github.com:xxeonN22/pv247-homework-scripts.git```

#### 2. Navigate to the folder of cloned repository  
```cd pv247-homework-scripts```

#### 3. Make the scripts executable
```chmod +x run_script.sh && chmod +x klonovanie_py```

#### 4. Run the script without arguments to see how to run the script
```./run_script.sh```

#### 5. Run the script with arguments
If u dont want to be moved to the `cloned_repos` directory automatically after cloning repositories  
```./run_script.sh "<HOMEWORK_URL>" "<HOMEWORK_FOLDER>" <NUMBER_OF_HOMEWORK>``` e.g.  

```./run_script.sh "https://pv247-app.vercel.app/lector/homeworks/styling?type=own" "styling" 3```

If u want to be moved to the `cloned_repos` directory automatically after cloning repositories   
```source run_script.sh "<HOMEWORK_URL>" "<HOMEWORK_FOLDER>" <NUMBER_OF_HOMEWORK>``` e.g.  

```source run_script.sh "https://pv247-app.vercel.app/lector/homeworks/styling?type=own" "styling" 3```

#### 6. Runing the script 

<details>
  <summary>This is how it looks like, when you will clone the repositories you havent reviewed yet.</summary>
  
  ![image](https://github.com/user-attachments/assets/854deb72-477d-4023-99d6-28b1aa962e82)
  
</details>

<details>
  <summary>This is how it looks like, when u already reviewed homeworks, but acidentally removed `reviewed_repos.txt` file.</summary>
  When the script will find out, that pull request contains `H(h)odnotenie` or `H(h)odnoceni` or `E(e)valuation` keyword, it will be marked as already reviewed and put inside `reviewed_repos.txt` file so it will not go through
the next time you will run the script.

![image](https://github.com/user-attachments/assets/b8401c29-fdb6-4d8d-98c0-213198299a8b)

</details>

<details>
  <summary>This is how it looks like, when runing script again when homeworks of the students were already evaluated</summary>
  When the script will find out, that pull request contains `H(h)odnotenie` or `H(h)odnoceni` or `E(e)valuation` keyword, it will be marked as already reviewed and put inside `reviewed_repos.txt` file so it will not go through
the next time you will run the script.

![image](https://github.com/user-attachments/assets/7e631e68-fab7-450c-96a7-9fd185f6d82a)

</details>

#### 7. Run the script to process repositories one by one
<details>
  <summary>After cloning repositories, you will see something like this</summary>

![image](https://github.com/user-attachments/assets/ecae9817-151b-4943-93e6-5a1b75afd209)

</details>

If u run the script using `source` you will be already inside `cloned_repos` folder as mentioned at 5th. step.
Now you can run another script `run_repos.sh` using either `dev` or `build`  

```./run_repos.sh build``` - suitable for first homework - typescript
 * Runing this should open VSC, open intergrated terminal, write npm install && npm run build, open URL with student's pull request

```./run_repos.sh dev```
 * Runing this should open VSC, open intergrated terminal, write npm install && npm run dev, open URL with student's pull request and also server on localhost:3000

<details>
  <summary>So it will look something like this :  </summary>
  When the script will find out, that pull request contains `H(h)odnotenie` or `H(h)odnoceni` or `E(e)valuation` keyword, it will be marked as already reviewed and put inside `reviewed_repos.txt` file so it will not go through
the next time you will run the script.

![image](https://github.com/user-attachments/assets/488a0d8f-9201-42d7-b20e-bad5162956bb)

</details>

As mentioned earlier, it will open VSC with intergrated terminal where it will put the command either `npm install && npm run build` or `npm install && npm run dev` based on the argument when runing script.
It will process repositories on by one - it will open also URL with pull request of given student and the live server if the `dev` argument is present.
You can then review the homework. After you are done, you should press `Enter` key to proceed to the next repository. 
You should not touch anything during opening etc. because certain things need to be focused to work properly.

After pressing `Enter`, the repository will be added to the `processed_repos.txt` file so it will not go through the next time you will run the script.

