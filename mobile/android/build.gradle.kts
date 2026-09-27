allprojects {
    repositories {
        google()
        mavenCentral()
    }
}

val newBuildDir: Directory =
    rootProject.layout.buildDirectory
        .dir("../../build")
        .get()
rootProject.layout.buildDirectory.value(newBuildDir)

subprojects {
    val newSubprojectBuildDir: Directory = newBuildDir.dir(project.name)
    project.layout.buildDirectory.value(newSubprojectBuildDir)

    // mapbox_maps_flutter 2.31.x assumes AGP 9's built-in Kotlin support. This
    // project intentionally keeps android.builtInKotlin=false, so apply the
    // already-declared Kotlin Android plugin to that subproject explicitly.
    // Remove this bridge once the upstream plugin handles that combination.
    if (name == "mapbox_maps_flutter") {
        pluginManager.apply("org.jetbrains.kotlin.android")
    }
}
subprojects {
    project.evaluationDependsOn(":app")
}

tasks.register<Delete>("clean") {
    delete(rootProject.layout.buildDirectory)
}
