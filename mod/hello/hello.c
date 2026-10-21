#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/init.h>

static int __init hello_init(void)
{
	printk(KERN_INFO "tivo-kbuild: hello from a 3.3.8-2.5 out-of-tree module\n");
	return 0;
}
static void __exit hello_exit(void)
{
	printk(KERN_INFO "tivo-kbuild: goodbye\n");
}
module_init(hello_init);
module_exit(hello_exit);
MODULE_LICENSE("GPL");
MODULE_AUTHOR("roamio-re");
MODULE_DESCRIPTION("TiVo Roamio kernel build-env smoke test");
