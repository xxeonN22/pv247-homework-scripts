# How to run the scripts 

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

This is how it looks like, when you will clone the repositories you havent reviewed yet.

![image](https://github.com/user-attachments/assets/854deb72-477d-4023-99d6-28b1aa962e82)


This is how it looks like, when u already reviewed homeworks, but acidentally removed `reviewed_repos.txt` file. 

![image](https://github.com/user-attachments/assets/b8401c29-fdb6-4d8d-98c0-213198299a8b)


This is how it looks like, when runing script again when homeworks of the students were already evaluated

![image](https://github.com/user-attachments/assets/7e631e68-fab7-450c-96a7-9fd185f6d82a)

#### 7. Run the script to process repositories one by one

If u run the script using `source` you will be already inside `cloned_repos` folder as mentioned at 5th. step.
Now you can run another script `run_repos.sh` using either `dev` or `build`  

```./run_repos.sh build``` - suitable for first homework - typescript
 * Runing this should open VSC, open intergrated terminal, write npm install && npm run build, open URL with student's pull request
```./run_repos.sh dev```
 * Runing this should open VSC, open intergrated terminal, write npm install && npm run dev, open URL with student's pull request and also server on localhost:3000
