The files here are used to build a docker image suitable for Swarming.
Recommended usage is for lightweight bots running mainly swarming
trigger/collect.

The docker image
--------------------------
The `build.sh` script will create a local image named `swarm_docker` tagged
with the date and time of creation. The image itself is simply an Ubuntu
flavor (bionic as of writing this) with a number of packages and utilities
installed. When launched as a container, this image is configured to run the
[start_swarm_bot.sh](https://chromium.googlesource.com/infra/infra/+/master/docker/swarm_docker/start_swarm_bot.sh)
script here which fetches and runs the bot code of the swarming server pointed
to by the `$SWARM_URL` env var. Note that running the image locally on a
developer workstation is unsupported.

### Automatic image building
Everyday at 8am PST, a builder on the internal.infra.cron waterfall builds a
fresh version of the image. This [builder](https://ci.chromium.org/p/infra-internal/builders/luci.infra-internal.prod/swarm-docker-image-builder)
essentially runs `./build.sh` and uploads the resultant image to a docker
[container registry](https://docs.docker.com/registry/). The registry, hosted
by gcloud, is located at
[chromium-container-registry](https://console.cloud.google.com/gcr/images/chromium-container-registry/GLOBAL/swarm_docker).

***note
For **arm64** images, the process is a little different. Its
[builder](https://ci.chromium.org/p/infra/builders/ci/swarm-docker-arm64-image-builder)
doesn't run on a schedule. Instead, when you need it to create a new image,
simply trigger it via the
[luci-scheduler UI](https://luci-scheduler.appspot.com/jobs/infra/swarm-docker-arm64-image-builder).
If you don't have the permissions to trigger a build, please file a Trooper bug
and someone can trigger it on your behalf.
***

### Shutting container down from within
Because a swarming bot may trigger a reboot of the bot at any time (see
[docs](https://cs.chromium.org/chromium/infra/luci/appengine/swarming/doc/Magic-Values.md?rcl=8b90cdd97f8f088bcba2fa376ce49d9863b48902&l=65)),
it should also be able to shut its container down from within. By conventional
means, that's impossible; a container has no access to the docker engine
running outside of it. Nor can it run many of the utilities in `/sbin/` since
the hardware layer of the machine is not available to the container. However,
because a swarming bot uses the `/sbin/shutdown` executable to reboot, this
file is replaced with our own bash script here
([shutdown.sh](https://chromium.googlesource.com/infra/infra/+/master/docker/swarm_docker/shutdown.sh))
that simply sends SIGUSR1 to `init` (pid 1). For a container, `init` is whatever
command the container was configured to run (as opposed to actual `/sbin/init`).
In our case, this is [start_swarm_bot.sh](https://chromium.googlesource.com/infra/infra/+/master/docker/swarm_docker/start_swarm_bot.sh),
which conveniently traps SIGUSR1 at the very beginning and exits upon catching
it. Consequently, running `/sbin/shutdown` from within a container will cause
the container to immediately shutdown.


Image deployment
--------------------------
Image deployment is done via puppet. When a new image needs to be rolled out,
grab the image name in the step-text of the "Push image" step on the
[image-building bot](https://ci.chromium.org/p/infra-internal/builders/luci.infra-internal.prod/swarm-docker-image-builder).
It should look like swarm_docker:$date. (The bot runs once a day, but you can
manually trigger a build if you don't want to wait.) To deploy, update the
image pins in puppet for [canary bots](https://chrome-internal.googlesource.com/infra/puppet/+/c9a06caeac7e236ac9e20e4f97c267faf53bf7ab/puppetm/opt/puppet/conf/nodes.yaml#778),
followed by [stable bots](https://chrome-internal.googlesource.com/infra/puppet/+/c9a06caeac7e236ac9e20e4f97c267faf53bf7ab/puppetm/opt/puppet/conf/nodes.yaml#1159).
The canary pin affects bots on [chromium-swarm-dev](https://chromium-swarm-dev.appspot.com),
which is not used by any builders, but can be used for manual testing before
updating stable pin. Please trigger a build on this bot by manually editing a
normal swarmbucket request sent to a multibot and making it execute on
[chromium-swarm-dev](https://chromium-swarm-dev.appspot.com). If the build looks
fine, you can proceed to update the stable pin. (Note that it may take several
hours for the image pin update to propagate. It's advised to wait at least a day
to update stable after updating canary.)

Launching the containers
------------------------
On the bots, container launching and managing is controlled via the python
service [here](https://chromium.googlesource.com/infra/infra/+/master/infra/services/swarm_docker/),
which ensures that a configured number of containers is running. It will
gracefully tear down containers that are too old or reboot the host. Called
every 5 minutes via cron.

More information can be found [here](https://chromium.googlesource.com/infra/infra/+/master/infra/services/swarm_docker/README.md).
